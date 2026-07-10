# 02 · Stack Tecnológica e Requisitos

## Linguagem
- **Python 3.10+** (validado em 3.14).

## Dependências (`requirements.txt`)

| Pacote | Papel |
|---|---|
| `fastapi` | Framework web da nossa API |
| `uvicorn[standard]` | Servidor ASGI que roda o FastAPI |
| `python-dotenv` | Carrega o arquivo `.env` |
| `httpx` | Cliente HTTP assíncrono (nossa API ↔ Defense IA) |
| `pycryptodome` | Criptografia do login (RSA PKCS#1 v1.5, AES/CBC, MD5) |
| `opencv-python-headless` | Lê o RTSP e gera os frames MJPEG (somente `/stream`) |
| `numpy` | Dependência do OpenCV |

> Se você só usar o endpoint `/rtsp` (retorno do link), o OpenCV/numpy são
> opcionais — o decode roda no lado cliente.

## Hardware

- Servidor com **RTX 4080 16GB** roda isto com folga, inclusive fazendo proxy
  MJPEG de várias câmeras simultâneas.
- Recomendações para muitas câmeras:
  - Prefira `/rtsp` e deixe o decode no cliente (mais leve para esta máquina).
  - Para `/stream`, ajuste `STREAM_FPS_LIMIT`, `STREAM_JPEG_QUALITY` e use
    `stream_type=2` (substream) quando full-res não for necessário.

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # e preencha IP/usuário/senha
```

## Execução

```bash
python main.py
# ou
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Rede / portas

| Porta | Quem | Configurável em |
|---|---|---|
| `8000` | Nossa API (cliente acessa) | `.env` → `API_PORT` |
| `80` / `443` | Defense IA (HTTP/HTTPS) | `.env` → `DEFENSE_PORT` |
| `9100` (ex.) | RTSP do Defense IA | definido pelo próprio Defense |
