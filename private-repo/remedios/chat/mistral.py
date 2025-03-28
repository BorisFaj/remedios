import os
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

access_token = os.getenv("HF_TOKEN")
# Nombre del repositorio y archivo del modelo
repo_id="Boritsuki/Mistral-Nemo-Instruct-2407-Q4_K_M-GGUF"
filename = "mistral-nemo-instruct-2407-q4_k_m.gguf"

# Descargar el modelo si no está en la caché
model_path = hf_hub_download(repo_id=repo_id, filename=filename, token=access_token)

# Cargar el modelo con llama_cpp
llm = Llama(model_path=model_path)


def ask(chat_history: str) -> str:
    response = llm(
        prompt=chat_history,
        max_tokens=150,  # Número máximo de tokens en la respuesta
        temperature=0.7,  # Hace respuestas más variadas
        top_p=0.9,  # Filtra palabras improbables
        top_k=50,  # Evita palabras irrelevantes
        repeat_penalty=1.2,  # Reduce repeticiones
        stop=["\n"]  # Detener generación en nueva línea
    )
    # Extraer y devolver la respuesta generada
    return response["choices"][0]["text"].strip()
