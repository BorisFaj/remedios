from gpt4all import GPT4All

# Ver lista de modelos disponibles
print(GPT4All.list_models())

# Nombre del modelo que se descargará automáticamente
model_name = "ggml-llama-3.2-1b-instruct"

gpt = GPT4All(model_name)
print("Modelo descargado correctamente")

model_path = "/home/ubuntu/models/ggml-llama-3.2-1b-instruct.bin"
gpt = GPT4All(model_path)

response = gpt.generate("Hola, ¿cómo estás?", max_tokens=100)
print(response)
