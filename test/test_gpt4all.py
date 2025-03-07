from gpt4all import GPT4All
import os

# Obtener la lista de modelos
available_models = GPT4All.list_models()

# Buscar el modelo de LLaMA 3 8B en la lista
model_name = None
for model in available_models:
    if "Llama 3 8B Instruct" in model["name"]:  # Busca por nombre parcial
        model_name = model["filename"]
        break

if not model_name:
    raise Exception("No se encontró el modelo de LLaMA 3 8B en la lista de modelos disponibles.")

print(f"Modelo encontrado: {model_name}")

# Cargar el modelo automáticamente
gpt = GPT4All(model_name)
print("Modelo cargado correctamente.")

# Generar una respuesta
response = gpt.generate("Hola, ¿cómo estás?", max_tokens=100)
print("Respuesta del modelo:", response)
