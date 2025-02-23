#!/bin/bash

# En principio era un entry_point, ahora es mas bien una chuleta pero no la voy a borrar aun
# Variables

echo "🚀 Actualizando el sistema..."
sudo apt update -y && sudo apt upgrade -y

echo "🔧 Instalando Docker y Docker Compose..."
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
sudo chmod 666 /var/run/docker.sock

echo "🔧 Instalando Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

echo "📁 Creando directorio para Kafka y Zookeeper..."
mkdir -p ~/kafka

# Copiar yaml
echo "🚀 Levantando Kafka y Zookeeper con Docker Compose..."
docker-compose up -d

echo "🔍 Verificando contenedores en ejecución..."
docker ps

echo "✅ Instalación y configuración completadas. Kafka está corriendo en la IP: $(curl -s ifconfig.me)"

docker exec -it kafka kafka-topics.sh --create --topic whatsapp-events --bootstrap-server $(curl -s ifconfig.me):9092 --partitions 1 --replication-factor 1

echo "✅ Topic whatsapp-events creado"

# El servidor de flask
sudo apt install -y python3 python3-pip python3-virtualenv
virtualenv venv
source venv/bin/activate

pip3 install flask confluent-kafka dotenv
mkdir ~/whatsapp-kafka

echo "PUBLIC_IP=$(curl -s ifconfig.me)" > .secrets
echo "WEBHOOK_VERIFY_TOKEN=845dr489fdgj46fgj4615" >> .secrets



###

sudo apt install -y certbot

sudo certbot certonly --standalone -d remediosapi.duckdns.org

sudo apt install -y python3-certbot-nginx curl nginx



