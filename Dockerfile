FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

WORKDIR /app

COPY bot /app/bot
COPY main.py requirements.txt IMG_2905.PNG /app/

RUN mkdir -p /app/data

CMD ["python", "main.py"]
