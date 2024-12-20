# Proyecto: Remedios

## Descripción
Este proyecto integra la API de WhatsApp de Meta con un servidor local Flask, expuesto a internet mediante ngrok, para procesar mensajes de texto y audio utilizando modelos de inteligencia artificial. Además, se conecta a un servidor GPT4All para generar respuestas dinámicas y contextuales. Aunque el sistema actual no utiliza un broker de mensajería, se contempla la incorporación futura de Kafka para mejorar la escalabilidad y la arquitectura del sistema.

![Diagrama de la arquitectura](/diagrama.webp)

## Arquitectura del Proyecto

El flujo principal de datos sigue estos pasos:

1. **API de WhatsApp**: Recibe y envía mensajes desde la plataforma de WhatsApp. Se comunica con `miApp` mediante un webhook.
2. **Ngrok**: Expone el servidor local `miApp` a internet, facilitando la comunicación con la API de WhatsApp.
3. **miApp (Flask)**:
   - Procesa mensajes de texto y audio.
   - Ejecuta modelos de inteligencia artificial para generar y procesar contenido.
   - Interactúa con el servidor GPT4All para obtener respuestas basadas en IA.
4. **GPT4All**: Proporciona respuestas contextuales basadas en el contenido del mensaje recibido.

### Diagrama de Arquitectura

```mermaid
graph TD
    subgraph WhatsApp
        A[WhatsApp API]
    end
    A -->|Webhook| B[Ngrok]
    B --> C[miApp (Flask)]
    C -->|Procesamiento IA| D[Modelos IA]
    C -->|Consulta| E[GPT4All]
    subgraph Futuro
        F[Kafka (Planeado)]
    end
    A -.->|Mensajería Escalable| F
    F -.->|Intermediario| C
```

## Requisitos

- Python 3.8+
- Flask
- Ngrok
- GPT4All
- Bibliotecas adicionales para modelos IA (especificadas en `requirements.txt`)

## Instalación y Configuración

1. Clona este repositorio:
   ```bash
   git clone https://github.com/tu-usuario/whatsapp-ai-assistant.git
   cd whatsapp-ai-assistant
   ```

2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Configura Ngrok para exponer el servidor local:
   ```bash
   ngrok http 5000
   ```
   Copia la URL generada por ngrok y configúrala como webhook en la API de WhatsApp.

4. Inicia el servidor Flask:
   ```bash
   python app.py
   ```

## Uso

- Envía mensajes de texto o audio a través de WhatsApp.
- El servidor procesará los mensajes y generará respuestas contextuales utilizando modelos de IA.

## Contribuciones

¡Las contribuciones son bienvenidas! Si tienes ideas para mejorar este proyecto, no dudes en abrir un issue o enviar un pull request.

## Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo `LICENSE` para más detalles.

## Disclaimer

Cualquier parecido con la realidad es pura coincidencia.

---

¡Esperamos que disfrutes experimentando con este proyecto y explorando las posibilidades de integrar IA en WhatsApp!
