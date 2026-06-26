# Defense IA → YOLO — Middle-Layer API

Microsserviço **FastAPI (orientado a objetos)** que abstrai a complexidade da
plataforma **Intelbras Defense IA 3.2** (login criptografado RSA/MD5/AES +
gestão de sessão) e entrega o feed das câmeras de forma simples para a equipe
que processa **YOLO**.

```
Defense IA  ->  esta API  ->  YOLO
```

## Estrutura do projeto

```
api_defense/
├── .env                  # << porta, IP, usuário e senha do Defense (preencha)
├── .env.example
├── main.py               # entrypoint (uvicorn)
├── requirements.txt
├── app/                  # aplicação POO
│   ├── config.py         # Settings (config via .env)
│   ├── crypto.py         # DefenseCrypto (MD5 / RSA / AES)
│   ├── defense_client.py # DefenseManager (sessão + StartVideo)
│   ├── streaming.py      # VideoStreamer (RTSP -> MJPEG)
│   ├── web.py            # WebApplication (FastAPI + rotas + dashboard)
│   └── static/index.html # painel navegável
├── knowledge/            # conhecimento para IA (endpoints, stack, auth, vídeo)
└── docs/
    ├── code/             # documentação de cada módulo de código
    └── Defense API 3.2 2.pdf
```

## 1. Configurar (`.env`)

Edite o arquivo **`.env`** — é nele que ficam **porta, endereço IP, usuário e
senha** da autenticação com o Defense:

```ini
DEFENSE_IP=192.168.1.1
DEFENSE_PORT=80
DEFENSE_USERNAME=system
DEFENSE_PASSWORD=troque_aqui
API_PORT=8000        # porta da NOSSA API (a que o YOLO acessa)
```

## 2. Instalar e rodar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py                  # ou: uvicorn main:app --host 0.0.0.0 --port 8000
```

## 3. Documentação (única interface)

Esta é uma **API pura**, sem frontend. A interface é o Swagger:

| URL | O quê |
|---|---|
| `http://localhost:8000/docs` | Swagger — explorar e testar os endpoints |
| `http://localhost:8000/` | Redireciona para `/docs` |
| `http://localhost:8000/health` | Status da sessão Defense IA |

## Endpoints

### Listar câmeras por unidade
```
GET /api/v1/cameras?online_only=true
-> {"total": N, "units": [{"code","name","cameras":[{channel_code, channel_name, online}]}]}
```

### Link RTSP direto
```
GET /api/v1/cameras/{channel_id}/rtsp?stream_type=1
-> {"channel_id": "...", "rtsp_url": "rtsp://...?token=..."}
```

### Stream MJPEG (HTTP)
```
GET /api/v1/cameras/{channel_id}/stream?stream_type=1
```
```python
import cv2
cap = cv2.VideoCapture("http://servidor:8000/api/v1/cameras/1000040$1$0$0/stream")
```

> `channel_id` = `channelCode` do Defense (ex.: `1000040$1$0$0`).
> `stream_type`: `1` principal, `2` secundário (mais leve para inferência).
> O token RTSP é de **uso único / ~30s**: para reconectar, chame de novo.

## Documentação

- **Conhecimento de domínio** (endpoints, stack, criptografia, vídeo): [`knowledge/`](knowledge/README.md)
- **Documentação do código** (um doc por módulo): [`docs/code/`](docs/code/README.md)

## Decode por GPU (dezenas de câmeras)

Para escalar o `/stream` na RTX, troque o motor de decode para FFmpeg/NVDEC:
```ini
STREAM_ENGINE=ffmpeg
STREAM_HWACCEL=cuda
FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe   # build com CUDA (gyan.dev "full")
```
- **Windows nativo** (recomendado p/ este servidor): `python main.py`.
- **Docker + GPU** (Linux/WSL2): `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build`.

Detalhes e ajustes em [knowledge/08_gpu_decode.md](knowledge/08_gpu_decode.md).

## Notas (RTX 4080)

- `/rtsp` é o mais leve (decode roda no YOLO) — ideal para muitas câmeras.
- `/stream` com `STREAM_ENGINE=ffmpeg`+`cuda` move o decode para a GPU; ajuste
  `STREAM_SCALE_WIDTH` / `STREAM_OUTPUT_FPS` / `STREAM_JPEG_QUALITY` / `stream_type=2`.
