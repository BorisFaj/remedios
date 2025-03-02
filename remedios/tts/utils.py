import io
import scipy

from pydub import AudioSegment


def wav_2_mp3(wav, sample_rate):
    _wav_file = io.BytesIO(wav)
    _mp3_file = io.BytesIO(wav)
    scipy.io.wavfile.write(_wav_file, rate=sample_rate, data=wav)

    # Read a file in
    sound = AudioSegment.from_wav(_wav_file)
    sound.export(_mp3_file, format='mp3')

    return _mp3_file