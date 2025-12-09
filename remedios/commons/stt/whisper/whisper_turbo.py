import os
import warnings

import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

# Selección de dispositivo
if torch.cuda.is_available():
    device = "cuda:0"
    torch_dtype = torch.float16
else:
    device = "cpu"
    torch_dtype = torch.float32
    warnings.warn("⚠️ No se encontró una GPU disponible. Ejecutando en CPU, esto será más lento.")

# Modelo configurable por env (fallback a un modelo más pequeño)
whisper_model_id = os.getenv("WHISPER_MODEL", "BorisFaj/whisperL-v3-turbo")
whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
    whisper_model_id, torch_dtype=torch_dtype, use_safetensors=True
).to(device)

processor = AutoProcessor.from_pretrained(whisper_model_id)


def transcribe(file_name) -> str:
    pipe = pipeline(
        "automatic-speech-recognition",
        model=whisper_model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=torch_dtype,
        device=device,
    )

    with torch.inference_mode():
        result = pipe(file_name, return_timestamps=True, generate_kwargs={"language": "spanish"})

    return result["text"]