import requests
import json
import os
from huggingface_hub import hf_hub_download

access_token = os.getenv("HF_TOKEN")
# Nombre del repositorio y archivo del modelo
repo_id="Boritsuki/Mistral-Nemo-Instruct-2407-Q4_K_M-GGUF"
filename = "mistral-nemo-instruct-2407-q4_k_m.gguf"

# Descargar el modelo si no está en la caché
model_path = hf_hub_download(repo_id=repo_id, filename=filename, token=access_token)

# Configuración del servidor llama.cpp
SERVER_URL = "http://localhost:8000/v1/completions"  # Cambia si tu servidor está en otro puerto o dirección

def ask(texto):
    """
    Envía un texto al servidor llama.cpp y devuelve la respuesta generada.

    Args:
        texto (str): El texto o prompt que se enviará al modelo.

    Returns:
        str: La respuesta generada por el modelo.
    """
    try:
        # Cuerpo de la solicitud
        payload = {
            "prompt": texto,
            "max_tokens": 150,  # Número máximo de tokens en la respuesta
            "temperature": 0.7,  # Hace respuestas más variadas
            "top_p": 0.9,  # Filtra palabras improbables
            "top_k": 50,  # Evita palabras irrelevantes
            "repeat_penalty": 1.2,  # Reduce repeticiones
            "stop": ["\n"]  # Detener generación en nueva línea
            }

        # Cabecera opcional para autenticación (si es necesaria)
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer no-key"  # Cambia si usas una clave API
        }

        # Realizar la solicitud POST al servidor
        response = requests.post(SERVER_URL, headers=headers, data=json.dumps(payload))

        # Verificar si la solicitud fue exitosa
        if response.status_code == 200:
            # Extraer el contenido generado del JSON de respuesta
            respuesta = response.json()
            return respuesta["choices"][0]["text"].strip()
        else:
            # Manejar errores
            return f"Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"Error al conectar con el servidor: {str(e)}"
