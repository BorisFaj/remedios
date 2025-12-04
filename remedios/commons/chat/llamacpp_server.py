import requests
import json

SERVER_URL = "http://llama:8000/completion"

def ask(texto):
    try:
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
        response = requests.post(SERVER_URL, headers=headers, data=json.dumps(payload), timeout=10)

        # Verificar si la solicitud fue exitosa
        if response.status_code == 200:
            # Extraer el contenido generado del JSON de respuesta
            respuesta = response.json()
            return respuesta["content"]
        else:
            # Manejar errores
            return f"Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"Error al conectar con el servidor: {str(e)}"
