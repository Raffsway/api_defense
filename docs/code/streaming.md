# `app/streaming.py` — `CameraStream` + `CameraHub`

## Responsabilidade
Converter fluxos **RTSP** em **MJPEG** sobre HTTP, otimizado para **várias
câmeras e vários espectadores simultâneos** no navegador, com **captura
compartilhada**: uma única conexão RTSP + um único decode por câmera, servindo
N espectadores.

## Por que compartilhar a captura
Antes, cada requisição `/stream` abria seu próprio `VideoCapture` e rodava um
gerador bloqueante no threadpool. Com muitas abas/câmeras isso multiplicava
conexões RTSP, decodificações e ameaçava esgotar o threadpool do FastAPI.

Agora:
- **10 navegadores na mesma câmera = 1 decode** (não 10).
- Geradores **assíncronos** não consomem threads do pool → escala.
- A captura **sobe no 1º espectador** e **cai após o último sair** (carência).

## Configuração de import
```python
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
```
Força RTSP sobre TCP (mais estável) antes de importar `cv2`.

## Dois motores de decode (`STREAM_ENGINE`)
`CameraStream._run` despacha entre:
- **`_run_opencv`** (padrão): `cv2.VideoCapture` + `cv2.imencode` (decode na CPU).
- **`_run_ffmpeg`**: subprocesso `ffmpeg` com `-f image2pipe -c:v mjpeg`; com
  `STREAM_HWACCEL=cuda` o decode roda na **GPU (NVDEC)**. `_extract_jpegs` separa
  os JPEGs do stdout (marcadores `FFD8..FFD9`) e publica o último frame.

`_build_ffmpeg_cmd` monta o comando (hwaccel, `-vf scale`, `-r fps`, `-q:v` a
partir de `STREAM_JPEG_QUALITY`). Detalhes e ajuste de GPU em
[knowledge/08_gpu_decode.md](../../knowledge/08_gpu_decode.md).

## `CameraStream` — captura de uma câmera (1 thread, N espectadores)
- Roda um **thread dedicado** que: pede a URL RTSP fresca ao Defense
  (`_acquire_url`), abre o `VideoCapture`, lê frames e mantém sempre o **último
  frame JPEG** em memória (`_latest`, com `_version` incremental).
- `subscribe()` é um **gerador assíncrono**: cada espectador acorda a
  `STREAM_OUTPUT_FPS`, e quando o `_version` muda, faz `yield` do frame.
- **Reconexão automática**: ao acumular `MAX_CONSECUTIVE_FAILURES` (30) falhas,
  reabre o RTSP (com backoff).
- **Encerramento por ociosidade**: sem espectadores por `STREAM_IDLE_GRACE`
  segundos, o thread libera a captura.
- **Timeout de 1º frame**: se nenhum frame chega em `STREAM_FIRST_FRAME_TIMEOUT`,
  o gerador encerra (câmera morta/erro) para não deixar o `<img>` pendurado.

### Ponte thread ↔ event loop
O thread (síncrono) precisa de uma URL RTSP nova, mas `start_video` é assíncrono.
Resolve-se com:
```python
asyncio.run_coroutine_threadsafe(url_provider(channel_id, stream_type), loop).result(...)
```

## `CameraHub` — registro de capturas
- `mjpeg_stream(channel_id, stream_type)` → gerador assíncrono pronto para o
  `StreamingResponse`. Reaproveita o `CameraStream` de `(canal, stream_type)`;
  cria um novo só se não existir ou estiver morto.
- `content_type` → `multipart/x-mixed-replace; boundary=frame`.
- `stats()` → lista das capturas ativas (exposto em `/health`).
- `shutdown()` → para todas as capturas (chamado no shutdown da app).

## Parâmetros (`.env`)
| Variável | Efeito |
|---|---|
| `STREAM_JPEG_QUALITY` | Qualidade do JPEG (1–100) |
| `STREAM_OUTPUT_FPS` | FPS reemitido por espectador (mural: 10–15) |
| `STREAM_IDLE_GRACE` | Segundos vivo após o último espectador |
| `STREAM_FIRST_FRAME_TIMEOUT` | Limite p/ o 1º frame antes de encerrar |

## Decisões de projeto
- Gerador **assíncrono** (não threadpool) para escalar em nº de espectadores.
- **Thread por câmera** porque a leitura do OpenCV é bloqueante.
- Buffer = 1 e RTSP/TCP priorizam **baixa latência** e estabilidade.
