import logging
import os
import tempfile
from pathlib import Path
from typing import Iterable, Union

import ffmpeg
import importlib
import subprocess
import sys
from huggingface_hub import hf_hub_download


def _import_whispercpp():
    try:
        from whispercpp import Whisper, api as whisper_api  # type: ignore
        return Whisper, whisper_api
    except Exception as exc:
        if "invalid ELF header" not in str(exc):
            raise
        # Intento de recompilar en la arquitectura actual
        reinstall_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-cache-dir",
            "--no-binary",
            "whispercpp",
            "whispercpp",
        ]
        logger.warning("whispercpp falló al importar (%s); reintentando instalación en runtime", exc)
        subprocess.check_call(reinstall_cmd)
        from whispercpp import Whisper, api as whisper_api  # type: ignore
        return Whisper, whisper_api


Whisper, whisper_api = _import_whispercpp()

logger = logging.getLogger(__name__)

WHISPER_FAKE = os.getenv("WHISPER_FAKE") == "1"

# Configuración de modelo
WHISPER_MODEL_REPO = os.getenv("WHISPER_MODEL_REPO", "ggerganov/whisper.cpp")
WHISPER_MODEL_FILE = os.getenv("WHISPER_MODEL_FILE", "ggml-large-v3-turbo-q5_0.bin")
WHISPER_MODEL_PATH = os.getenv("WHISPER_MODEL", WHISPER_MODEL_FILE)
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "es")

_whisper_model = None  # cache perezoso


def _reinstall_and_reload():
    """Reinstala whispercpp en runtime (p. ej. si la .so tiene ELF erróneo) y recarga módulos."""
    reinstall_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--force-reinstall",
        "--no-cache-dir",
        "--no-binary",
        "whispercpp",
        "whispercpp",
    ]
    logger.warning("whispercpp falló; reintentando reinstalación en runtime")
    subprocess.check_call(reinstall_cmd)
    import whispercpp  # noqa: WPS433

    importlib.reload(whispercpp)
    globals()["Whisper"] = whispercpp.Whisper  # type: ignore
    globals()["whisper_api"] = whispercpp.api  # type: ignore


def _init_whisper_from_file(local_path: str) -> "Whisper":
    """
    Crea una instancia de Whisper con un modelo custom (no limitado a MODELS_URL).
    Replica la lógica de from_pretrained pero usando un path local.
    """
    _ref = object.__new__(Whisper)
    try:
        context = whisper_api.Context.from_file(local_path, no_state=False)
    except Exception as exc:
        if "invalid ELF header" not in str(exc):
            raise
        _reinstall_and_reload()
        context = whisper_api.Context.from_file(local_path, no_state=False)
    params = (
        whisper_api.Params.from_enum(whisper_api.SAMPLING_GREEDY)
        .with_print_progress(False)
        .with_print_realtime(False)
        .build()
    )
    context.reset_timings()
    _context_initialized = True
    _transcript: list[str] = []
    _ref.__dict__.update(locals())
    return _ref


def _load_model(model_path: str) -> "Whisper":
    if os.path.isfile(model_path):
        return _init_whisper_from_file(model_path)
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
            return _init_whisper_from_file(local_path)
        except Exception as exc:
            last_exc = exc
            logger.warning("No se pudo descargar %s/%s: %s", WHISPER_MODEL_REPO, candidate, exc)
    if last_exc:
        raise last_exc
    raise RuntimeError("No se encontraron candidatos de modelo para whisper.cpp")


def _get_model() -> "Whisper":
    if WHISPER_FAKE:
        raise RuntimeError("WHISPER_FAKE está activo; no se carga el modelo real")

    global _whisper_model
    if _whisper_model is None:
        _whisper_model = _load_model(WHISPER_MODEL_PATH)
    return _whisper_model


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


def transcribe(audio: Union[str, bytes, bytearray]) -> str:
    if WHISPER_FAKE:
        return "transcription-disabled"

    wav_path = _to_wav_file(audio)
    try:
        model = _get_model()
        return model.transcribe_from_file(wav_path)
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            logger.warning("No se pudo eliminar el temporal de audio %s", wav_path)
