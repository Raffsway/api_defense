# 06 · Streaming de Vídeo (RTSP → MJPEG)

> Fonte: manual Defense API 3.2, seções 5.3 (Live View) e 6.2.4.2 (StartVideo).
> Implementado em `app/streaming.py` (`VideoStreamer`).

## Como o Defense entrega vídeo

1. Chamar `StartVideo` → recebe `url` + `token`.
2. Montar `rtsp://...?token=...`.
3. Puxar o stream por RTSP (OPTIONS → DESCRIBE → SETUP → PLAY).

Características do token RTSP:
- **uso único** (invalida após o primeiro uso);
- expira em **~30s** se não for usado.

Por isso, **cada** pedido de vídeo chama `StartVideo` de novo para obter um
token fresco.

## Dois modos de consumo

### A) `/rtsp` — repassar o link (mais leve)
A nossa API só devolve o `rtsp_url`. O decode roda no cliente.
- Melhor para **muitas câmeras** (não consome CPU/GPU desta máquina).

### B) `/stream` — proxy MJPEG via OpenCV (captura compartilhada)
A nossa API abre o RTSP com OpenCV, lê os frames e os reemite como
`multipart/x-mixed-replace; boundary=frame` (MJPEG sobre HTTP).
- Mais fácil para o consumidor (abre até no browser).
- Consome CPU/GPU desta máquina (decode + re-encode JPEG).
- **Captura compartilhada:** N espectadores na mesma câmera = **1 conexão RTSP
  + 1 decode** (ver `CameraStream`/`CameraHub` em `app/streaming.py`). Ideal para
  exibir **várias câmeras** em um mural no navegador.

## Consumir várias câmeras no navegador (mural)
O painel (`/`) tem a seção **"Mural — várias câmeras"**: cole vários `channelId`
(um por linha), escolha o nº de colunas e o tipo de stream. Cada tile é um
`<img>` apontando para `/api/v1/cameras/{id}/stream`. Como a captura é
compartilhada, abrir a mesma câmera em várias abas **não** multiplica conexões
no Defense.

Recomendações para muitas câmeras no mural:
- Use **`stream_type=2`** (substream) — menor resolução/banda.
- Reduza **`STREAM_OUTPUT_FPS`** (ex.: 10–15) e **`STREAM_JPEG_QUALITY`**.

## Detalhes técnicos do proxy MJPEG

- Transporte RTSP forçado para **TCP** via
  `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp` (mais estável).
- `CAP_PROP_BUFFERSIZE = 1` → menor latência (sempre o frame mais recente).
- O gerador de frames é **síncrono**: o Starlette o executa em threadpool, sem
  bloquear o event loop.
- Encerra após `MAX_CONSECUTIVE_FAILURES` (30) falhas seguidas de leitura
  (ex.: token expirou, câmera caiu).

## Parâmetros de ajuste (`.env`)
| Variável | Efeito |
|---|---|
| `STREAM_JPEG_QUALITY` | Qualidade do JPEG (1–100). Menor = menos banda |
| `STREAM_FPS_LIMIT` | Limita FPS reemitido (`0` = sem limite) |
| `DEFENSE_DEFAULT_STREAM_TYPE` | `1` principal / `2` substream (default) |

## Recomendação para a RTX 4080
- Poucas câmeras → `/stream` à vontade.
- Muitas câmeras → prefira `/rtsp` e/ou `stream_type=2`, reduza
  `STREAM_JPEG_QUALITY`/`STREAM_FPS_LIMIT`.
