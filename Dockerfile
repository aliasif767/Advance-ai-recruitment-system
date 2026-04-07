FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p received_cvs

EXPOSE 8000

# Use shell form (not JSON array) so $PORT variable is expanded correctly
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}