import os

from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from transformers import BitsAndBytesConfig


model_id = "mistralai/Mistral-Nemo-Instruct-2407"
# model_id = "mistralai/Mistral-7B-Instruct-v0.3"
access_token = os.getenv("HF_TOKEN")

tokenizer = AutoTokenizer.from_pretrained(model_id, token=access_token)

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16
)

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    torch_dtype=torch.float16,
    device_map="auto",
    token=access_token
)

def ask(chat_history: str) -> str:
    # Asegurar que el modelo tenga `pad_token_id` configurado correctamente
    model.config.pad_token_id = model.config.eos_token_id
    inputs = tokenizer(chat_history, return_tensors="pt").to("cuda")
    # Eliminar token_type_ids si está presente
    inputs.pop("token_type_ids", None)

    outputs = model.generate(
        **inputs,
        max_new_tokens=150,
        temperature=0.7,  # Hace respuestas más variadas
        top_p=0.9,  # Filtra palabras improbables
        top_k=50,  # Evita palabras irrelevantes
        repetition_penalty=1.2,  # Reduce repeticiones
        do_sample=True  # ¡ACTIVA SAMPLE PARA QUE FUNCIONE!
    )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True, clean_up_tokenization_spaces=True).strip()

    response = response.split("[Remedios]:")[-1]

    return response
