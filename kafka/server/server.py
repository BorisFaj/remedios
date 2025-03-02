from flask import Flask, request, jsonify
from confluent_kafka import Producer
import json
import socket
import os
import boto3
import time
import sys
import logging

# Forzar que los prints se muestren inmediatamente en los logs de Docker
sys.stdout.reconfigure(line_buffering=True)

# Redirigir logs de Flask a stdout para que se vean en Docker logs
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Configuración de Kafka
KAFKA_BROKER = "kafka:9092"
TOPIC = "whatsapp-events"

# Configurar el productor de Kafka
producer_conf = {
    "bootstrap.servers": KAFKA_BROKER,
    "client.id": socket.gethostname(),
}
producer = Producer(producer_conf)

## Funciones para AWS
AWS_REGION = "eu-north-1"

cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
lambda_client = boto3.client("lambda", region_name=AWS_REGION)

def enviar_metricas():
    """Envía a CloudWatch la cantidad de mensajes procesados en Kafka"""
    print("📊 Enviando métrica a CloudWatch...")

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

        print(f"✅ Métrica enviada con éxito. Respuesta: {response}")

    except Exception as e:
        print(f"❌ Error al enviar métrica a CloudWatch: {e}")


def invoke_lambda():
    """Llama a la Lambda para encender la instancia si está apagada"""
    print("🔹 Intentando invocar la Lambda desde Flask...")
    try:
        payload = {"source": "flask"}
        response = lambda_client.invoke(
            FunctionName="ControlEC2",
            InvocationType="Event",
            Payload=json.dumps(payload)
        )
        result = response["Payload"].read()
        print(f"✅ Lambda ejecutada con éxito. Respuesta: {result}")
    except Exception as e:
        raise Exception(f"❌ Error al invocar la Lambda: {e}")


# Inicializar Flask
app = Flask(__name__)

@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode and token and challenge:  # Asegurar que todos los valores existen
            if mode == "subscribe" and token == os.environ.get("WEBHOOK_VERIFY_TOKEN"):
                app.logger.info("Webhook verified successfully!")
                return challenge, 200
            else:
                return jsonify({"status": "error", "message": "Invalid verification token"}), 403
        else:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400

    elif request.method == "POST":
        try:
            if request.content_type != "application/json":
                return jsonify({"status": "error", "message": "Unsupported Media Type"}), 415

            data = request.get_json(silent=True)  # Evitar que Flask lance una excepción si no es JSON

            if not data:
                return jsonify({"status": "error", "message": "No JSON received"}), 400

            print("Mensaje recibido:", json.dumps(data, indent=2))

            # Enviar el mensaje a Kafka
            producer.produce(TOPIC, json.dumps(data))
            producer.flush()

            # Enviar metricas
            enviar_metricas()
            # Llamar lambda
            invoke_lambda()

            return jsonify({"status": "success"}), 200

        except Exception as e:
            print("Error:", str(e))
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "Invalid request"}), 400  # En caso de que no entre en GET o POST

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000, debug=True)
