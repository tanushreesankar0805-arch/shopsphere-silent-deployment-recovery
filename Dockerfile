
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

COPY router.py /app/router.py
COPY detector.py /app/detector.py
COPY controller.py /app/controller.py
COPY incident_store.py /app/incident_store.py

# Copy automated tests into the container
COPY tests/ /app/tests/

EXPOSE 5000 8080 9100

CMD ["python", "app/main.py"]
