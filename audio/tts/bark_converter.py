from bark import SAMPLE_RATE, generate_audio, preload_models
from audio.utils import wav_2_mp3

# download and load all models
preload_models()

# generate audio from text
def convert(text):
    audio_array = generate_audio(text)
    return wav_2_mp3(audio_array, sample_rate=SAMPLE_RATE)
