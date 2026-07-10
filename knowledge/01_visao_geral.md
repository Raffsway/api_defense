# 01 · Visão Geral

## Objetivo

Microsserviço **"Middle-Layer"** que abstrai toda a complexidade da plataforma
**Intelbras Defense IA 3.2** (autenticação criptografada e gestão de sessão) e
entrega o feed de vídeo das câmeras de forma simples para uma equipe terceira
(cliente).

```
┌────────────┐     login RSA/MD5/AES      ┌──────────────────┐     RTSP / MJPEG (HTTP)     ┌──────────┐
│ Defense IA │ <───── keepalive ───────── │  Middle-Layer    │ ─────────────────────────►  │ Cliente  │
│   3.2      │ ─────  StartVideo ───────► │  (FastAPI/POO)   │                             │  (time)  │
└────────────┘                            └──────────────────┘                             └──────────┘
```

## Por que existe

A API nativa do Defense IA exige:
- login em **duas etapas** com assinatura MD5 (5 iterações) + RSA + AES;
- **heartbeat** a cada ~22s e renovação de token a cada ~22min;
- montagem manual da URL RTSP com token de uso único.

A equipe cliente **não** deveria lidar com nada disso. Esta camada faz tudo e
expõe dois endpoints triviais: pegar o link RTSP ou consumir o vídeo já em HTTP.

## Arquitetura (POO)

| Componente | Classe | Responsabilidade |
|---|---|---|
| `app/config.py` | `Settings` | Configuração via `.env` |
| `app/crypto.py` | `DefenseCrypto` | MD5 / RSA / AES |
| `app/defense_client.py` | `DefenseManager` | Sessão + StartVideo + re-login |
| `app/streaming.py` | `VideoStreamer` | RTSP → MJPEG |
| `app/web.py` | `WebApplication` | FastAPI, rotas e dashboard |
| `main.py` | — | Entrypoint (uvicorn) |

## Fluxo de uma requisição

1. No **startup**, `WebApplication` faz login e inicia o keepalive em background.
2. A equipe cliente chama `GET /api/v1/cameras/{channel_id}/rtsp` (ou `/stream`).
3. `DefenseManager.start_video()` chama `StartVideo` no Defense IA com o token vivo.
4. O Defense devolve `url` + `token`; montamos `rtsp://...?token=...`.
5. Retornamos o link (rtsp) **ou** abrimos o RTSP e transmitimos MJPEG (stream).

## Acesso

- Painel navegável: `http://<host>:8000/`
- Swagger: `http://<host>:8000/docs`
- Healthcheck: `http://<host>:8000/health`
