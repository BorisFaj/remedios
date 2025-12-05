import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Union

import ffmpeg
import httpx
from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

WHISPER_FAKE = os.getenv("WHISPER_FAKE") == "1"

# Configuración de modelo
WHISPER_MODEL_REPO = os.getenv("WHISPER_MODEL_REPO", "ggerganov/whisper.cpp")
WHISPER_MODEL_FILE = os.getenv("WHISPER_MODEL_FILE", "ggml-large-v3-turbo-q5_0.bin")
WHISPER_MODEL_PATH = os.getenv("WHISPER_MODEL", WHISPER_MODEL_FILE)
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "es")
WHISPER_CLI = os.getenv("WHISPER_CLI", "/usr/local/bin/whispercpp-cli")
WHISPER_SERVER_URL = os.getenv("WHISPER_SERVER_URL", "http://127.0.0.1:9000")

_resolved_model_path: str | None = None


def _ensure_cli() -> str:
    if not WHISPER_CLI:
        raise RuntimeError("WHISPER_CLI no está configurado")
    if os.path.isfile(WHISPER_CLI):
        return WHISPER_CLI

    resolved = shutil.which(WHISPER_CLI)
    if resolved:
        return resolved

    raise RuntimeError(f"No se encontró el binario whisper.cpp en {WHISPER_CLI}")


def _resolve_model_path(model_path: str) -> str:
    global _resolved_model_path
    if _resolved_model_path:
        return _resolved_model_path

    if os.path.isfile(model_path):
        _resolved_model_path = model_path
        return _resolved_model_path

    logger.warning("Modelo Whisper.cpp no encontrado en %s, se intentará resolverlo de forma automática", model_path)

    candidates = []
    name = Path(model_path).name
    if "." in name:
        candidates.append(name)
    else:
        candidates.extend([f"{name}.bin", f"{name}.gguf"])

    last_exc = None
    for candidate in candidates:
        try:
            local_path = hf_hub_download(
                repo_id=WHISPER_MODEL_REPO,
                filename=candidate,
                local_files_only=False,
            )
            _resolved_model_path = local_path
            return _resolved_model_path
        except Exception as exc:
            last_exc = exc
            logger.warning("No se pudo descargar %s/%s: %s", WHISPER_MODEL_REPO, candidate, exc)
    if last_exc:
        raise last_exc
    raise RuntimeError("No se encontraron candidatos de modelo para whisper.cpp")


def _to_wav_file(audio: Union[str, bytes, bytearray]) -> str:
    """Normaliza entrada (bytes/ruta) a un wav 16k mono temporal para whisper.cpp."""
    if isinstance(audio, (bytes, bytearray)):
        audio_bytes = bytes(audio)
    elif isinstance(audio, str):
        with open(audio, "rb") as src:
            audio_bytes = src.read()
    else:
        audio_bytes = audio.read()

    if not audio_bytes:
        raise ValueError("Audio vacío o no válido para transcribir")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as wav_file:
        wav_path = wav_file.name

    try:
        (
            ffmpeg.input("pipe:0")
            .output(wav_path, format="wav", ac=1, ar="16k")
            .overwrite_output()
            .run(input=audio_bytes, capture_stdout=True, capture_stderr=True, quiet=True)
        )
    except ffmpeg.Error as exc:  # pragma: no cover - depende de ffmpeg
        stderr = exc.stderr.decode("utf-8", "ignore") if getattr(exc, "stderr", None) else str(exc)
        logger.error("ffmpeg falló al convertir audio: %s", stderr)
        os.unlink(wav_path)
        raise

    return wav_path


def _collect_text(segments: Union[str, Iterable]) -> str:
    if isinstance(segments, str):
        return segments.strip()

    pieces = []
    for segment in segments:
        text = getattr(segment, "text", None)
        if text:
            pieces.append(text)
    return " ".join(pieces).strip()


def _transcribe_via_server(wav_path: str) -> str:
    url = WHISPER_SERVER_URL.rstrip("/") + "/inference"
    with open(wav_path, "rb") as fh:
        files = {"file": ("audio.wav", fh, "audio/wav")}
        try:
            resp = httpx.post(url, files=files, timeout=180)
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

    wav_path = _to_wav_file(audio)
    try:
        if WHISPER_SERVER_URL:
            return _transcribe_via_server(wav_path)

        cli_path = _ensure_cli()
        model_path = _resolve_model_path(WHISPER_MODEL_PATH)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_base = os.path.join(tmpdir, "out")
            cmd = [
                cli_path,
                "-m",
                model_path,
                "-f",
                wav_path,
                "-l",
                WHISPER_LANGUAGE,
                "-otxt",
                "-of",
                output_base,
            ]
            try:
                completed = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                logger.error("whisper.cpp CLI falló: %s", exc.stderr or exc.stdout)
                raise RuntimeError("Error al transcribir con whisper.cpp CLI") from exc

            txt_file = f"{output_base}.txt"
            if not os.path.exists(txt_file):
                logger.error("whisper.cpp no generó salida .txt; stdout=%s", completed.stdout)
                raise RuntimeError("No se generó transcripción")

            with open(txt_file, "r", encoding="utf-8", errors="ignore") as fh:
                return _collect_text(fh.read())
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            logger.warning("No se pudo eliminar el temporal de audio %s", wav_path)
