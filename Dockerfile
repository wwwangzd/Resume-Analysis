FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY config ./config
COPY src ./src
COPY utils ./utils

EXPOSE 8999

CMD ["uvicorn", "src.script:app", "--host", "0.0.0.0", "--port", "8999"]
