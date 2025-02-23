FROM python:3.10-slim

WORKDIR /app

RUN pip3 install --no-cache-dir flask confluent-kafka

COPY server.py /app/server.py
COPY requirements.txt /app/requirements.txt

EXPOSE 3000

CMD ["pip3 install -r /app/requirements.txt"]
CMD ["python3", "/app/server.py"]

