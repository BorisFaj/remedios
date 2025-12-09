import os

backend = os.environ.get("WHISPER_BACKEND", "cpp")

if backend == "cpp":
    from .whisper_cpp import *
elif backend == "turbo":
    from .whisper_turbo import *
else:
    raise ValueError(f"Whisper backend desconocido: {backend}")
