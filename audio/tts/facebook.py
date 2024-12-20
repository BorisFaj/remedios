from transformers import VitsModel, AutoTokenizer
import torch
import scipy
import numpy as np
from audio.utils import wav_2_mp3


model = VitsModel.from_pretrained("facebook/mms-tts-spa")
tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-spa")

def generate_audio(text):

    inputs = tokenizer(text, return_tensors="pt")

    with torch.no_grad():
        output = model(**inputs).waveform

    data_np = output.numpy()
    data_np_squeezed = np.squeeze(data_np)

    # scipy.io.wavfile.write("output/respuesta.wav", rate=model.config.sampling_rate, data=data_np_squeezed)

    return wav_2_mp3(data_np_squeezed, sample_rate=model.config.sampling_rate)