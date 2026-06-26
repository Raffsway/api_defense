# 10 · Consumindo o RTSP Corretamente (token de uso único)

> **Leia antes de integrar vídeo via RTSP.** Esta observação evita o erro mais
> comum ao consumir o serviço (player pedindo usuário/senha).

## A regra de ouro do Defense

O endpoint `GET /api/v1/cameras/{channel_id}/rtsp` devolve algo como:
```
rtsp://<host>:9100/dss/monitor/param/cameraid=...substream=2?token=271939
```
O `?token=...` é gerado pelo Defense e tem **duas restrições**:
- **Uso único** — vale para **UMA** conexão; ao ser usado, é consumido.
- **Expira em ~30 s** se não for usado.

**Consequência:** o link RTSP **NÃO pode ser copiado/colado e reutilizado**.
Se o token já foi usado ou venceu, o servidor RTSP do Defense passa a **exigir
usuário/senha** — é por isso que o VLC abre um prompt de login. Não é falha da
API; é o comportamento do Defense.

---

## Qual caminho usar

| Objetivo | Endpoint | Token | Reutilizável? | Login? |
|---|---|---|---|---|
| Apenas **visualizar** (VLC, navegador, dashboard) | `/stream` (MJPEG) | a API gerencia | **Sim** | Não |
| **Integração** que exige `rtsp://` (IA/YOLO, NVR, gravador) | `/rtsp` | uso único | Não | Só se vencer |

### Regra prática
> Para **ver**, use `/stream`. Para **processar/gravar em RTSP nativo**, use
> `/rtsp` **gerando um token novo a cada conexão** (nunca reaproveite o link).

---

## Soluções de código (consumo correto)

### A) Visualizar — VLC ou navegador (MJPEG, reutilizável, sem login)
```
http://SEU_SERVIDOR:8000/api/v1/cameras/{channel_id}/stream?stream_type=2
```
VLC: *Mídia → Abrir Fluxo de Rede* → cole a URL. Ou abra direto no navegador.

### B) IA / YOLO consumindo RTSP nativo (Python + OpenCV)
Gera um token novo a cada (re)conexão — este é o padrão correto:
```python
import cv2, requests, time

API     = "http://SEU_SERVIDOR:8000"
CHANNEL = "1000167$1$0$0"
STREAM  = "2"  # 1=principal, 2=secundario

def fresh_rtsp() -> str:
    r = requests.get(f"{API}/api/v1/cameras/{CHANNEL}/rtsp",
                     params={"stream_type": STREAM}, timeout=15)
    r.raise_for_status()
    return r.json()["rtsp_url"]

def open_capture() -> cv2.VideoCapture:
    # abre IMEDIATAMENTE apos gerar o link (token de uso unico / ~30s)
    return cv2.VideoCapture(fresh_rtsp(), cv2.CAP_FFMPEG)

cap = open_capture()
while True:
    ok, frame = cap.read()
    if not ok:                      # caiu? pega um token NOVO e reconecta
        cap.release()
        time.sleep(1)
        cap = open_capture()
        continue
    # ... rodar a inferencia YOLO no frame ...
```
> ❌ **Errado:** guardar o `rtsp_url` em uma variável/config e reusar.
> ✅ **Certo:** chamar `/rtsp` de novo a cada conexão/reconexão.

### C) RTSP nativo no VLC (uso pontual) — gerar e abrir juntos
PowerShell (Windows): gera o token e abre o VLC no mesmo instante.
```powershell
$ch = '1000167$1$0$0'
$r = Invoke-RestMethod "http://SEU_SERVIDOR:8000/api/v1/cameras/$ch/rtsp?stream_type=2"
Start-Process "C:\Program Files\VideoLAN\VLC\vlc.exe" -ArgumentList $r.rtsp_url
```

### D) FFmpeg (gravar/transcodificar) — também gerar na hora
```bash
URL=$(curl -s "http://SEU_SERVIDOR:8000/api/v1/cameras/1000167%241%240%240/rtsp?stream_type=2" \
      | python -c "import sys,json;print(json.load(sys.stdin)['rtsp_url'])")
ffmpeg -rtsp_transport tcp -i "$URL" -c copy saida.mp4
```

---

## Resumo para quem comercializa / integra
1. Documente para o cliente: **o link RTSP é de uso único** — não copie/cole/reuse.
2. Para **monitoramento**, entregue a URL `/stream` (estável, sem login).
3. Para **IA/gravação em RTSP**, o consumidor deve chamar `/rtsp` **a cada
   conexão** (exemplo B). Reaproveitar o link causa prompt de login no player.
