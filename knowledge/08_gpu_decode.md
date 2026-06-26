# 08 · Decode por GPU e Escala (Dezenas de Câmeras)

> Implementado em `app/streaming.py` (`CameraStream._run_ffmpeg`).

## O gargalo real
Com muitas câmeras, o custo dominante é **decodificar H.264/H.265**. No motor
OpenCV (CPU) isso satura o processador por volta de uma dúzia de câmeras em alta
resolução. A solução é mover o decode para a **GPU (NVDEC da RTX)**.

## Dois motores de decode (`STREAM_ENGINE`)
| Motor | Decode | Quando usar |
|---|---|---|
| `opencv` (padrão) | CPU | Poucas câmeras; sem ffmpeg/GPU |
| `ffmpeg` | CPU **ou GPU (NVDEC)** | Muitas câmeras; escala |

Ambos alimentam a **captura compartilhada** (1 conexão/decode por câmera) e o
mesmo gerador MJPEG assíncrono — só muda quem decodifica.

## Como o motor ffmpeg funciona
Para cada câmera, sobe um processo:
```
ffmpeg -rtsp_transport tcp [-hwaccel cuda] -i <rtsp> -an \
       [-vf scale=W:-2] [-r FPS] -f image2pipe -c:v mjpeg -q:v Q pipe:1
```
- `-hwaccel cuda` → **decode na GPU (NVDEC)**, liberando a CPU.
- A saída é uma sequência de JPEGs que a API separa (marcadores `FFD8..FFD9`) e
  publica como último frame para os espectadores.
- `-r` limita o FPS na origem (menos trabalho), `-q:v` controla a qualidade,
  `scale` reescala (opcional).

## Configuração (`.env`)
```ini
STREAM_ENGINE=ffmpeg        # ativa o motor ffmpeg
STREAM_HWACCEL=cuda         # NVDEC (RTX); use "none" p/ CPU
FFMPEG_PATH=ffmpeg          # ou C:\ffmpeg\bin\ffmpeg.exe no Windows
STREAM_SCALE_WIDTH=0        # ex.: 1280 reduz banda/CPU
STREAM_OUTPUT_FPS=15
STREAM_JPEG_QUALITY=95
```

## Como habilitar a GPU

### A) Windows nativo (recomendado p/ este servidor)
1. Baixe um **ffmpeg com CUDA** (builds "full" do gyan.dev já incluem NVDEC).
2. Aponte `FFMPEG_PATH` para o `ffmpeg.exe`.
3. `STREAM_ENGINE=ffmpeg`, `STREAM_HWACCEL=cuda`.
4. `python main.py`. O decode roda na RTX.

### B) Docker + NVIDIA Container Toolkit (Linux/WSL2)
```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```
O override liga `STREAM_ENGINE=ffmpeg`/`cuda` e expõe a GPU ao container
(`NVIDIA_DRIVER_CAPABILITIES=video,...`). O ffmpeg da imagem (7.x) já suporta
`-hwaccel cuda` (lista em `ffmpeg -hwaccels`).

## Verificar se a GPU está em uso
- `nvidia-smi` deve mostrar processos `ffmpeg` e uso do **NVDEC**.
- Sem GPU disponível, o ffmpeg cai para decode em CPU (ainda funciona).

## Recomendações de escala (RTX 4080, dezenas de câmeras)
- `STREAM_ENGINE=ffmpeg` + `STREAM_HWACCEL=cuda`.
- No mural, use `stream_type=2` (substream) e `STREAM_SCALE_WIDTH=1280`.
- `STREAM_OUTPUT_FPS=10–15` por câmera.
- A NVDEC da 4080 decodifica dezenas de fluxos 1080p simultâneos com folga; os
  limites práticos passam a ser **banda de rede** e o **re-encode JPEG** (CPU) —
  ambos reduzidos por `scale`, `fps` e `quality`.
- Para zero re-encode (qualidade idêntica), o passo seguinte seria WebRTC/MSE
  com passthrough de H.264 (go2rtc) — evolução futura.
