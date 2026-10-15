FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

# Railway/Render/Oracle CI pass PORT env var
CMD ["sh", "-c", "gunicorn app:app -b 0.0.0.0:${PORT:-8080} --workers 2 --timeout 60"]
