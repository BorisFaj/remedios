FROM python:3.10-slim

WORKDIR /app

COPY core/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY core/*.py /app/

EXPOSE 3000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:3000", "dispatcher:app"]
