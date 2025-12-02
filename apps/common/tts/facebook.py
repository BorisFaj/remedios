from transformers import VitsModel, AutoTokenizer
import torch
import numpy as np
from remedios.tts.utils import wav_2_mp3

model = VitsModel.from_pretrained("facebook/mms-stt-spa")
tokenizer = AutoTokenizer.from_pretrained("facebook/mms-stt-spa")

def generate_audio(text):

    inputs = tokenizer(text, return_tensors="pt")

    with torch.no_grad():
        output = model(**inputs).waveform

    data_np = output.numpy()
    data_np_squeezed = np.squeeze(data_np)

    return wav_2_mp3(data_np_squeezed, sample_rate=model.config.sampling_rate)