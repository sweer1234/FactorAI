FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

ENV FACTORAI_SQLITE_PATH=/data/factorai.db
ENV FACTORAI_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost

RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
