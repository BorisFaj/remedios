import logging
import os
import tempfile
import io
import wave
from typing import Union, Tuple

import ffmpeg
import requests

logger = logging.getLogger(__name__)

WHISPER_FAKE = os.getenv("WHISPER_FAKE") == "1"
WHISPER_TIMEOUT = os.getenv("WHISPER_TIMEOUT")
WHISPER_TIMEOUT = float(WHISPER_TIMEOUT) if WHISPER_TIMEOUT not in (None, "", "None") else None

# Configuración de modelo
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "es")
WHISPER_SERVER_URL = os.getenv("WHISPER_SERVER_URL", "http://127.0.0.1:9000")
WHISPER_SERVER_URL_CPP = os.getenv("WHISPER_SERVER_URL_CPP")  # opcional, para dual-call


def _to_wav_file(audio: Union[str, bytes, bytearray]) -> bytes:
    """Normaliza entrada (bytes/ruta) a un wav 16k mono y devuelve los bytes."""
    if isinstance(audio, (bytes, bytearray)):
        audio_bytes = bytes(audio)
    elif isinstance(audio, str):
        with open(audio, "rb") as src:
            audio_bytes = src.read()
    else:
        audio_bytes = audio.read()

    if not audio_bytes:
        raise ValueError("Audio vacío o no válido para transcribir")

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        (
            ffmpeg.input("pipe:0")
            .output(tmp_path, format="wav", ac=1, ar="16k")
            .overwrite_output()
            .run(input=audio_bytes, capture_stdout=True, capture_stderr=True, quiet=True)
        )

        with open(tmp_path, "rb") as wav_file:
            out = wav_file.read()
    except ffmpeg.Error as exc:  # pragma: no cover - depende de ffmpeg
        stderr = exc.stderr.decode("utf-8", "ignore") if getattr(exc, "stderr", None) else str(exc)
        logger.error("ffmpeg falló al convertir audio: %s", stderr)
        raise
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return out


def _transcribe_via_server(wav_bytes: bytes, url: str | None = None) -> str:
    target = (url or WHISPER_SERVER_URL).rstrip("/") + "/inference"

    def _parse_response(resp: requests.Response) -> str:
        try:
            data = resp.json()
            if data.get("error"):
                raise RuntimeError(data["error"])
            text = data.get("text") or data.get("result") or ""
            if text:
                return text.strip()
        except Exception:
            pass
        return resp.text.strip()

    try:
        logger.info("Enviando audio a whisper-server %s", target)
        # Usa spooled temp para evitar disco en audios pequeños; log si se vuelca a disco
        with tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024, suffix=".wav") as tmp:
            tmp.write(wav_bytes)
            tmp.seek(0)
            if getattr(tmp, "_rolled", False):
                logger.info("WAV spooled a disco (size=%d bytes)", len(wav_bytes))
            files = {"file": ("audio.wav", tmp, "audio/wav")}
            resp = requests.post(target, files=files, timeout=WHISPER_TIMEOUT)
            logger.info("Respuesta whisper-server: status=%s", resp.status_code)
            resp.raise_for_status()
            return _parse_response(resp)
    except Exception as exc:  # pragma: no cover - network/runtime
        logger.error("whisper-server falló: %s", exc)
        raise RuntimeError("Error al transcribir con whisper-server") from exc


def _wav_duration_seconds(wav_bytes: bytes) -> float | None:
    """Calcula la duración del WAV en segundos usando su cabecera."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            if frames > 0 and rate > 0:
                return frames / float(rate)
    except Exception:
        logger.debug("No se pudo calcular duración del WAV", exc_info=True)
    return None


def transcribe(audio: Union[str, bytes, bytearray]) -> Tuple[str, float | None]:
    if WHISPER_FAKE:
        return "transcription-disabled"

    if not WHISPER_SERVER_URL:
        raise RuntimeError("WHISPER_SERVER_URL no está definido; whisper-server es obligatorio")

    wav_bytes = _to_wav_file(audio)
    duration = _wav_duration_seconds(wav_bytes)
    return _transcribe_via_server(wav_bytes), duration
