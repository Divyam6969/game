FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend
COPY tests /app/tests
COPY sample_data.py /app/sample_data.py

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]


