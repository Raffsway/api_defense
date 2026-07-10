# 05 · Endpoints Externos (Equipe Cliente → Nossa API)

Base URL: `http://{API_HOST}:{API_PORT}` (ex.: `http://servidor:8000`).
Definidos em `app/web.py` (`WebApplication`).

## `GET /` — Redirect
Redireciona para `/docs` (Swagger). Esta é uma API pura, sem frontend.

## `GET /health` — Healthcheck
```json
{
  "status": "ok",
  "version": "1.0.0",
  "defense_base_url": "http://192.168.1.1:80",
  "defense_authenticated": true,
  "user_id": "1",
  "active_streams": [
    {"channel_id": "1000041$1$0$0", "stream_type": "2", "subscribers": 3, "alive": true}
  ]
}
```
`active_streams` lista as capturas compartilhadas vivas e quantos espectadores
cada uma tem (uma captura serve N espectadores).

## `GET /api/v1/cameras`
Lista as câmeras (canais encoder) **agrupadas por unidade**, para preencher o
mural sem digitar IDs. Combina `tree/deviceOrg` (nomes das unidades) e
`tree/devices` (canais com nome).

**Query params:** `online_only` (bool; só câmeras online).

**Resposta 200:**
```json
{
  "total": 3209,
  "units": [
    {
      "code": "001001011",
      "name": "Aracaju",
      "cameras": [
        {"channel_code": "1000094$1$0$0", "channel_name": "CAJU - 01 - Sala de convivencia", "device_name": "...", "online": true}
      ]
    }
  ]
}
```

## `GET /api/v1/cameras/{channel_id}/rtsp`
Retorna o link RTSP direto da câmera.

**Query params:** `stream_type` (`1` principal | `2` secundário; default do `.env`).

**Resposta 200:**
```json
{
  "channel_id": "1000040$1$0$0",
  "rtsp_url": "rtsp://192.168.1.1:9100/vms/monitor/param/cameraid=1000040%240%26substream=1?token=2204"
}
```
⚠️ **Token de uso único / ~30s:** não copie/reuse o `rtsp_url`. Gere um token
novo **a cada conexão**. Padrões de consumo (IA/VLC/ffmpeg) em
[10_consumo_rtsp.md](10_consumo_rtsp.md).

Consumo no cliente (gerando token novo a cada reconexão):
```python
import cv2, requests
def fresh(): return requests.get(f"{API}/api/v1/cameras/{CH}/rtsp",
                                 params={"stream_type":"2"}).json()["rtsp_url"]
cap = cv2.VideoCapture(fresh(), cv2.CAP_FFMPEG)   # abrir imediatamente
```

## `GET /api/v1/cameras/{channel_id}/stream`
Proxy HTTP **MJPEG** (`multipart/x-mixed-replace`). Não precisa lidar com RTSP.

**Query params:** `stream_type` (`1` | `2`).

Consumo:
```html
<img src="http://servidor:8000/api/v1/cameras/1000040$1$0$0/stream">
```
```python
import cv2
cap = cv2.VideoCapture("http://servidor:8000/api/v1/cameras/1000040$1$0$0/stream")
```

## Códigos de status da nossa API
| HTTP | Significado |
|---|---|
| `200` | OK |
| `502` | Defense IA respondeu erro de negócio (ex.: canal inválido) |
| `503` | Defense IA inacessível (conexão/timeout) |
| `500` | Erro interno inesperado |

## Observações importantes
- O token RTSP é de **uso único / ~30s**: para reconectar, chame o endpoint de novo.
- `channel_id` contém `$` — ao montar a URL no código, faça `encodeURIComponent`/quote.
- Para inferência mais leve/rápida no cliente, use `stream_type=2`.
