FROM python:3.10-slim

WORKDIR /app

RUN pip3 install --no-cache-dir flask confluent-kafka boto3

COPY server.py /app/server.py
COPY requirements.txt /app/requirements.txt

EXPOSE 3000

CMD ["python3", "/app/server.py"]
