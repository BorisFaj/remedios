FROM python:3.10-slim

WORKDIR /app

COPY apps/webhook/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/webhook/server.py ./server.py

EXPOSE 3000

CMD ["python", "server.py"]
