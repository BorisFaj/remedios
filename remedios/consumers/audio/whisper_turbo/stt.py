import functools
import os
from typing import Tuple

import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

_whisper_model_id = os.getenv("WHISPER_MODEL", "BorisFaj/whisperL-v3-turbo")


@functools.lru_cache(maxsize=1)
def _get_pipeline():
    """Carga perezosa del modelo/pipeline para evitar descargas en import."""
    import warnings

    if torch.cuda.is_available():
        device = "cuda:0"
        torch_dtype = torch.float16
    else:
        device = "cpu"
        torch_dtype = torch.float32
        warnings.warn("⚠️ No se encontró una GPU disponible. Ejecutando en CPU, esto será más lento.")

    whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
        _whisper_model_id, torch_dtype=torch_dtype, use_safetensors=True
    ).to(device)
    processor = AutoProcessor.from_pretrained(_whisper_model_id)
    return pipeline(
        "automatic-speech-recognition",
        model=whisper_model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=torch_dtype,
        device=device,
    )


def transcribe(file_name) -> Tuple[str, float | None]:
    """Devuelve (texto, duracion_s|None) usando los timestamps del pipeline."""
    pipe = _get_pipeline()

    with torch.inference_mode():
        result = pipe(file_name, return_timestamps=True, generate_kwargs={"language": "spanish"})

    text = result.get("text", "") or ""
    duration = None
    chunks = result.get("chunks") or []
    if chunks and isinstance(chunks, list):
        last = chunks[-1]
        if isinstance(last, dict):
            ts = last.get("timestamp")
            if isinstance(ts, (list, tuple)) and len(ts) == 2 and ts[1] is not None:
                duration = float(ts[1])

    return text, duration
