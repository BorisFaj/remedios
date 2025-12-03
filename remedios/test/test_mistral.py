import os

from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from dotenv import find_dotenv, load_dotenv
from transformers import BitsAndBytesConfig

load_dotenv(find_dotenv(".env"))

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Ejecutando en: {device}")

model_id = "mistralai/Mistral-7B-Instruct-v0.3"
access_token = os.getenv("HF_TOKEN")

tokenizer = AutoTokenizer.from_pretrained(model_id, use_auth_token=access_token)

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16
)

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    torch_dtype=torch.float16,
    device_map="auto",
    use_auth_token=access_token
)

chat_history = """[contexto] Eres un asistente muy útil, te llamas Remedios.
[user] Cuentame un chiste.
[Remedios] Por que un ordenador cogio una moneda? Porque no le quedaba ninguna ventana abierta!
[user] JaJa, cuentame otro.
[Remedios]"""

inputs = tokenizer(chat_history, return_tensors="pt").to("cuda")
outputs = model.generate(
    **inputs,
    max_new_tokens=100,
    temperature=0.7,  # Hace respuestas más variadas
    top_p=0.9,  # Filtra palabras improbables
    top_k=50,  # Evita palabras irrelevantes
    repetition_penalty=1.2,  # Reduce repeticiones
    do_sample=True  # ¡ACTIVA SAMPLE PARA QUE FUNCIONE!
)



response = tokenizer.decode(outputs[0], skip_special_tokens=True)
response = response.split("[Remedios]")[-1]

print(response)