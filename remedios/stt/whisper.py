import torch

from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline


device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

whisper_model_id = "openai/whisper-large-v3-turbo"

whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
    whisper_model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True
)

whisper_model.to(device)

def transcribe(file_name) -> str:
    processor = AutoProcessor.from_pretrained(whisper_model_id)

    pipe = pipeline(
        "automatic-speech-recognition",
        model=whisper_model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=torch_dtype,
        device=device,
    )

    result = pipe(file_name, return_timestamps=True, generate_kwargs={"language": "spanish"})
    return result["text"]
