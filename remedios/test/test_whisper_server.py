from pathlib import Path
from remedios.commons.stt.whisper.whisper_cpp import _transcribe_via_server, _to_wav_file


_AUDIO_PATH = Path(__file__).parent / "audio_descargado.ogg"


def _load_wav_bytes() -> bytes:
    raw = _AUDIO_PATH.read_bytes()
    return _to_wav_file(raw)

def test_transcribe_via_server():
    wav = _load_wav_bytes()
    transcription = _transcribe_via_server(wav)
    print(transcription)
    assert not "error" in transcription
