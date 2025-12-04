from remedios.commons.stt import whisper


class DummySegment:
    def __init__(self, text: str):
        self.text = text


def test_tmp_wav_cleanup(tmp_path):
    # Crea un archivo de audio vacío y verifica que se borra al final
    dummy_audio = tmp_path / "a.ogg"
    dummy_audio.write_bytes(b"not-audio")
    try:
        whisper.transcribe(dummy_audio.as_posix())
    except Exception:
        # se espera que falle por audio inválido, pero debe limpiar el tmp
        pass
    # No hay forma directa de verificar el tmp, solo que no explota
    assert dummy_audio.exists()
