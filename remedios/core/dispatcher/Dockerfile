FROM python:3.10-slim

ARG APP_SRC=remedios
ENV VENV=/app/.venv
ENV PYTHONPATH=/app

WORKDIR /app

COPY ${APP_SRC}/ /app/${APP_SRC}/

RUN pip install --no-cache-dir -r /app/${APP_SRC}/requirements.txt
RUN pip install --no-cache-dir -r /app/${APP_SRC}/core/dispatcher/requirements.txt

EXPOSE 3000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:3000", "remedios.core.dispatcher.producer:app"]
