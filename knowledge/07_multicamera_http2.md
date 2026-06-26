# 07 · Várias Câmeras numa Aba (HTTP/2)

## O problema
Cada câmera no mural é um `<img>` MJPEG, e **cada MJPEG mantém uma conexão HTTP
aberta permanentemente**. Navegadores limitam **~6 conexões por host em
HTTP/1.1**. Logo, com 10 câmeras numa aba, só ~6 abrem e as demais **travam**.

## A solução: HTTP/2 via Caddy
O **HTTP/2 multiplexa** muitos streams sobre uma única conexão (centenas de
streams concorrentes), eliminando o limite de 6. Colocamos o **Caddy** como
reverse proxy HTTP/2 na frente da API.

```
Defense IA → api-defense (MJPEG) → Caddy (HTTP/2 + TLS) → navegador (10+ <img>)
```

### Por que TLS é obrigatório
Os navegadores **só falam HTTP/2 sobre TLS** (não existe h2 em texto puro). Por
isso o Caddy serve **HTTPS** usando sua **CA interna** (`tls internal`): o
certificado é auto-assinado e o navegador pede para confiar **uma vez**.

### Detalhe crítico do proxy: `flush_interval -1`
No `Caddyfile`, `flush_interval -1` **desliga o buffer** do reverse proxy, para
cada frame MJPEG ser repassado imediatamente (sem isso o vídeo "engasga").

## Como acessar
| Acesso | URL | Uso |
|---|---|---|
| **Mural (navegador)** | `https://<host>:8443/` | Várias câmeras numa aba (HTTP/2) |
| API direta (HTTP/1.1) | `http://<host>:8000/` | Equipe YOLO / clientes programáticos |

> Na primeira visita a `https://<host>:8443/`, aceite o aviso de certificado
> (CA interna do Caddy). Opcional: instalar a raiz do Caddy (em
> `/data/caddy/pki/authorities/local/root.crt` dentro do volume `caddy_data`)
> para remover o aviso.

## Qualidade de imagem (MJPEG)
O MJPEG re-encoda em JPEG, então há **alguma** perda vs. o H.264 original. Para
maximizar a qualidade:
- `STREAM_JPEG_QUALITY=95` (alta qualidade).
- `STREAM_OUTPUT_FPS=25` para full-motion (ou 12–15 para aliviar com muitas câmeras).

> Para **zero** perda de qualidade seria necessário passthrough de H.264
> (WebRTC/MSE via go2rtc) — uma evolução possível desta arquitetura.

## Performance (RTX 4080, 10 câmeras)
- O custo aqui é **decode + re-encode JPEG** por câmera, na CPU/GPU desta máquina.
- Captura **compartilhada**: 1 decode por câmera, mesmo com a aba aberta em
  vários monitores/abas (ver [06_streaming_video.md](06_streaming_video.md)).
- Se a CPU apertar com 10 câmeras em alta qualidade: baixe `STREAM_OUTPUT_FPS`,
  use `stream_type=2` (substream) e/ou reduza `STREAM_JPEG_QUALITY`.
- Banda: MJPEG em alta qualidade é pesado; garanta rede gigabit entre servidor
  e quem assiste.
