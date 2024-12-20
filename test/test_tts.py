import io
from transformers import VitsModel, AutoTokenizer
import torch
import numpy as np
from pydub import AudioSegment
import scipy

def wav_2_mp3(wav):
    with io.BytesIO() as inmemoryfile:
        compression_format = 'mp3'
        n_channels = 2 if wav.shape[0] == 2 else 1 # stereo and mono files
        AudioSegment(wav.tobytes(), sample_width=wav.dtype.itemsize,
                     channels=n_channels).export(inmemoryfile, format=compression_format)
        return  np.array(AudioSegment.from_file_using_temporary_files(inmemoryfile) .get_array_of_samples())


model = VitsModel.from_pretrained("facebook/mms-tts-spa")
tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-spa")

text = "some example text in the Spanish language"
inputs = tokenizer(text, return_tensors="pt")

with torch.no_grad():
    output = model(**inputs).waveform

data_np = output.numpy()
data_np_squeezed = np.squeeze(data_np)

_wav_file = io.BytesIO(data_np_squeezed)
scipy.io.wavfile.write(_wav_file, rate=model.config.sampling_rate, data=data_np_squeezed)

# Read a file in
sound = AudioSegment.from_wav(_wav_file)
sound.export("converted.mp3", format='mp3')
