from llama_cpp import Llama

# Nombre del modelo en Hugging Face (puedes cambiarlo por otro compatible)
model_name = "TheBloke/Meta-Llama-3-8B-Instruct-GGUF"

# Descarga automática y carga en GPU
llm = Llama.from_pretrained(
    repo_id=model_name,
    filename="Meta-Llama-3-8B-Instruct.Q4_0.gguf",
    n_gpu_layers=-1  # Usar todas las capas en GPU
)

print("✅ Modelo descargado y cargado en GPU correctamente.")

# Probar una inferencia
response = llm("¿Cuál es la capital de Francia?")
print("GPT responde:", response)
