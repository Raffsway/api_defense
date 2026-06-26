# Imagem base enxuta com Python.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libglib2.0-0: runtime do OpenCV. ffmpeg: motor de decode alternativo
# (STREAM_ENGINE=ffmpeg). Para NVDEC/GPU, use docker-compose.gpu.yml + NVIDIA
# Container Toolkit (o ffmpeg do Debian carrega libnvcuvid via runtime nvidia).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Instala dependencias primeiro (melhor cache de camadas).
COPY requirements.txt .
RUN pip install -r requirements.txt

# Codigo da aplicacao.
COPY . .

# Porta interna fixa (o mapeamento para o host fica no docker-compose).
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
