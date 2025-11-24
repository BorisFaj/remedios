from flask import Flask, request, jsonify
import socket
from zordon import KafkaProducer
import json
import boto3
import time
import sys
import logging
from dotenv import load_dotenv, find_dotenv
import os
import atexit

load_dotenv(find_dotenv(".env"))

# logs
sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Kafka
producer = KafkaProducer(
    bootstrap_servers=os.environ.get("BOOTSTRAP_SERVER"),
    security_protocol="SASL_SSL",
    sasl_mechanism="SCRAM-SHA-256",
    sasl_plain_username=os.environ.get("REDPANDA_USER"),
    sasl_plain_password=os.environ.get("REDPANDA_PASS"),
)
hostname = str.encode(socket.gethostname())

# AWS
AWS_REGION = "eu-north-1"
cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
lambda_client = boto3.client("lambda", region_name=AWS_REGION)

# Flask
app = Flask(__name__)

def on_success(metadata):
    app.logger.info(f"✅ Enviado a '{metadata.topic}' en offset {metadata.offset}")

def on_error(e):
  app.logger.info(f"❌ Error enviando mensaje a Kafka: {e}")

def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token and challenge:  # Asegurar que todos los valores existen
        if mode == "subscribe" and token == os.environ.get("WEBHOOK_VERIFY_TOKEN"):
            app.logger.info("✅ Webhook verificado correctamente")
            return challenge, 200
        else:
            return jsonify({"status": "error", "message": "Token de verificación inválido"}), 403
    return jsonify({"status": "error", "message": "Parámetros faltantes"}), 400


def get_topic(data):
    """Determina el topic correcto del mensaje."""

    changes = data["entry"][0].get("changes", [])
    value = changes[0].get("value", {})

    if "statuses" in value:
        return "whatsapp-text"

    message = value["messages"][0]
    message_type = message.get("type")

    if message_type == "text":
        return "whatsapp-text"
    elif message_type == "audio":
        return "whatsapp-audio"
    else:
        return "whatsapp-text"

def send_to_kafka(data, topic):
    """Encola el mensaje en Kafka."""

    for i in range(1):
        future = producer.send(
            topic,
            key=hostname,
            value=str.encode(data)
        )
        future.add_callback(on_success)
        future.add_errback(on_error)
    producer.flush()

def enviar_metricas():
    """Envía a CloudWatch la cantidad de mensajes procesados en Kafka."""
    app.logger.info("📊 Enviando métrica a CloudWatch...")

    try:
        response = cloudwatch.put_metric_data(
            Namespace="Custom/Kafka",
            MetricData=[
                {
                    "MetricName": "KafkaMessagesReceived",
                    "Dimensions": [{"Name": "InstanceId", "Value": "i-0509833f417865be9"}],  # Reemplázalo con tu ID real
                    "Timestamp": time.time(),
                    "Value": 1,  # Un mensaje recibido
                    "Unit": "Count"
                }
            ]
        )

        app.logger.info(f"✅ Métrica enviada con éxito. Respuesta: {response}")

    except Exception as e:
        app.logger.info(f"❌ Error al enviar métrica a CloudWatch: {e}")


def invoke_lambda():
    """Llama a la Lambda para encender la instancia si está apagada."""
    app.logger.info("🔹 Intentando invocar la Lambda desde Flask...")
    try:
        payload = {"source": "flask"}
        response = lambda_client.invoke(
            FunctionName="ControlEC2",
            InvocationType="Event",
            Payload=json.dumps(payload)
        )
        result = response["Payload"].read()
        app.logger.info(f"✅ Lambda ejecutada con éxito. Respuesta: {result}")
    except Exception as e:
        raise Exception(f"❌ Error al invocar la Lambda: {e}")


@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        return verificar_webhook()

    elif request.method == "POST":
        try:
            if request.content_type != "application/json":
                return jsonify({"status": "error", "message": "Unsupported Media Type"}), 415

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "No JSON received"}), 400

            app.logger.info("📩 Mensaje recibido:", json.dumps(data, indent=2))

            topic = get_topic(data)
            send_to_kafka(data, topic)
            enviar_metricas()
            # invoke_lambda()

            return jsonify({"status": "success", "topic": topic}), 200

        except Exception as e:
            app.logger.info("❌ Error:", str(e))
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "Invalid request"}), 400


def cerrar_kafka_producer():
    """Cierra el Kafka Producer al finalizar el programa."""
    app.logger.info("🔴 Cerrando Kafka Producer...")
    producer.close()

atexit.register(cerrar_kafka_producer)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000, debug=True)
