import os
import torch
import asyncio
import streamlit as st
from dotenv import find_dotenv, load_dotenv
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

os.environ["STREAMLIT_SERVER_RUN_ON_SAVE"] = "false"
# 🔹 Evitar errores de asyncio en Streamlit
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# 🔹 Cargar variables de entorno
load_dotenv(find_dotenv(".env"))
access_token = os.getenv("HF_TOKEN")

# 🔹 Configuración de página
st.set_page_config(page_title="Chat con Modelos HF", layout="wide")

# 🔹 Modelos disponibles (puedes agregar más aquí)
MODELOS_DISPONIBLES = {
    "Mistral-Nemo-2407": "mistralai/Mistral-Nemo-Instruct-2407",
    "Mistral-7B-Instruct-v0.3": "mistralai/Mistral-7B-Instruct-v0.3"
}

# 🔹 Sidebar para selección de modelo y parámetros
st.sidebar.title("Configuración del Modelo")
modelo_seleccionado = st.sidebar.selectbox("Selecciona un modelo", list(MODELOS_DISPONIBLES.keys()))
model_id = MODELOS_DISPONIBLES[modelo_seleccionado]

temperatura = st.sidebar.slider("Temperatura", 0.1, 2.0, 0.7, 0.1)
top_p = st.sidebar.slider("Top P", 0.1, 1.0, 0.9, 0.05)
top_k = st.sidebar.slider("Top K", 1, 100, 50, 1)
max_new_tokens = st.sidebar.slider("Máx. Tokens", 50, 512, 150, 10)

# 🔹 Cargar modelo y tokenizer con cache en Streamlit
@st.cache_resource
def cargar_modelo(model_id):
    try:
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

        return model, tokenizer

    except Exception as e:
        st.error(f"Error al cargar el modelo: {e}")
        return None, None


modelo, tokenizer = cargar_modelo(model_id)

# 🔹 Inicializar historial de chat si no existe
if "historial" not in st.session_state:
    st.session_state["historial"] = []


# 🔹 Función para generar respuesta del modelo
def generar_respuesta(mensaje):
    if modelo is None or tokenizer is None:
        return "⚠️ Error: No se pudo cargar el modelo."

    chat_history = "\n".join(st.session_state["historial"]) + f"\n[Usuario]: {mensaje}\n[Remedios]:"

    try:
        modelo.config.pad_token_id = modelo.config.eos_token_id
        inputs = tokenizer(chat_history, return_tensors="pt").to("cuda" if torch.cuda.is_available() else "cpu")
        inputs.pop("token_type_ids", None)

        outputs = modelo.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperatura,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=1.2,
            do_sample=True
        )

        respuesta = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        respuesta = respuesta.split("[Remedios]:")[-1]

        return respuesta

    except Exception as e:
        return f"⚠️ Error al generar la respuesta: {e}"


# 🔹 Interfaz de chat
st.title("🤖 Chat con Modelos Mistral")
st.write("Prueba diferentes modelos y parámetros.")

# 🔹 Mostrar historial de chat
for mensaje in st.session_state["historial"]:
    st.write(mensaje)

# 🔹 Entrada de usuario
mensaje_usuario = st.text_input("Escribe tu mensaje:")
if st.button("Enviar") and mensaje_usuario:
    respuesta = generar_respuesta(mensaje_usuario)

    # Guardar historial
    st.session_state["historial"].append(f"**Usuario:** {mensaje_usuario}")
    st.session_state["historial"].append(f"**Remedios:** {respuesta}")


    st.rerun()

