# whispercpp-go (prototipo)

Consumidor en Go que escucha `transcription_requests` en Kafka y envía el audio al `whisper-server` (whisper.cpp) sin pasar por Python. Calcula la duración a partir del WAV que genera `ffmpeg`.

## Requisitos
- Go 1.21+
- `ffmpeg` en el PATH (se usa para normalizar a WAV 16k mono)
- Broker Kafka accesible
- `whisper-server` levantado y accesible (HTTP)

## Variables de entorno principales
- `BOOTSTRAP_SERVER` (obligatorio) — host:puerto de Kafka
- `AUDIO_TOPIC` (opc) — por defecto `transcription_requests`
- `DLQ_TOPIC` (opc) — por defecto `remedios_dlq`
- `GROUP_ID` (opc) — por defecto `whatsapp-audio-consumer`
- `GRAPH_URL` y `GRAPH_API_TOKEN` (obligatorias) — para descargar el audio de Meta
- `WHISPER_SERVER_URL` (opc) — por defecto `http://127.0.0.1:9000`
- `FFMPEG_PATH` (opc) — binario de ffmpeg si no está en PATH
- `WHISPER_TIMEOUT` (opc) — segundos para timeout HTTP a whisper-server

## Build rápido
```bash
cd go/whispercpp
go mod tidy   # requiere red para resolver dependencias
GOOS=linux GOARCH=arm64 go build -o whispercpp-consumer .
```

## Ejecución
```bash
BOOTSTRAP_SERVER=kafka.kafka.svc.cluster.local:9092 \
GRAPH_URL=https://graph.facebook.com/v19.0 \
GRAPH_API_TOKEN=XXXX \
WHISPER_SERVER_URL=http://127.0.0.1:9000 \
./whispercpp-consumer
```

Pendiente: integrar update_job_status/save_job_result contra la base de datos (actualmente el flujo se queda en consumir → transcribir).
