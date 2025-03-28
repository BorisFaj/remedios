from transformers import AutoTokenizer, pipeline
import torch

# Cargar el modelo
model_name = "TinyLlama/TinyLlama_v1.1"
tokenizer = AutoTokenizer.from_pretrained(model_name)
pipeline = pipeline(
    "text-generation",
    model=model_name,
    torch_dtype=torch.float16,
    device_map="auto",
)

def ask(user_input):
    response = pipeline(
        user_input,
        do_sample=True,
        top_k=10,
        num_return_sequences=1,
        repetition_penalty=1.2,
        eos_token_id=tokenizer.eos_token_id,
        max_length=500,
    )

    return response[0]["generated_text"]
