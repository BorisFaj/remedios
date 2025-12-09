from pathlib import Path

from remedios.commons.stt import whisper

_AUDIO_PATH = Path(__file__).parent / "audio_descargado.ogg"


def _load_wav_bytes() -> bytes:
    raw = _AUDIO_PATH.read_bytes()
    return whisper._to_wav_file(raw)

def test_multipart_variants():
    wav = _load_wav_bytes()
    transcription = whisper._transcribe_via_server(wav)
    print(transcription)
    assert not "error" in transcription

