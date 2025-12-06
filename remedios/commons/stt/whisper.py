import logging
import os
from typing import Union

import ffmpeg
import httpx

logger = logging.getLogger(__name__)

WHISPER_FAKE = os.getenv("WHISPER_FAKE") == "1"

# Configuración de modelo
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "es")
WHISPER_SERVER_URL = os.getenv("WHISPER_SERVER_URL", "http://127.0.0.1:9000")


def _to_wav_file(audio: Union[str, bytes, bytearray]) -> str:
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
        out, _ = (
            ffmpeg.input("pipe:0")
            .output("pipe:1", format="wav", ac=1, ar="16k")
            .overwrite_output()
            .run(input=audio_bytes, capture_stdout=True, capture_stderr=True, quiet=True)
        )
    except ffmpeg.Error as exc:  # pragma: no cover - depende de ffmpeg
        stderr = exc.stderr.decode("utf-8", "ignore") if getattr(exc, "stderr", None) else str(exc)
        logger.error("ffmpeg falló al convertir audio: %s", stderr)
        raise

    return out


def _transcribe_via_server(wav_bytes: bytes) -> str:
    url = WHISPER_SERVER_URL.rstrip("/") + "/inference"
    files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
    try:
        logger.info("Enviando audio a whisper-server %s", url)
        resp = httpx.post(url, files=files, timeout=180)
        logger.info("Respuesta whisper-server: status=%s", resp.status_code)
        resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - network/runtime
        logger.error("whisper-server falló: %s", exc)
        raise RuntimeError("Error al transcribir con whisper-server") from exc

    try:
        data = resp.json()
        text = data.get("text") or data.get("result") or ""
        if text:
            return text.strip()
    except Exception:
        pass

    # fallback si devuelve texto plano
    return resp.text.strip()


def transcribe(audio: Union[str, bytes, bytearray]) -> str:
    if WHISPER_FAKE:
        return "transcription-disabled"

    if not WHISPER_SERVER_URL:
        raise RuntimeError("WHISPER_SERVER_URL no está definido; whisper-server es obligatorio")

    wav_bytes = _to_wav_file(audio)
    return _transcribe_via_server(wav_bytes)
