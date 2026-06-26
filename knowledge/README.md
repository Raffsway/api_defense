# Base de Conhecimento — Defense IA → YOLO Middle-Layer

Esta pasta reúne, em Markdown, todo o conhecimento necessário para uma **IA**
(ou um desenvolvedor) entender e operar este projeto sem precisar abrir o PDF
de 490 páginas do fabricante.

| Arquivo | Conteúdo |
|---|---|
| [01_visao_geral.md](01_visao_geral.md) | O que é o projeto, arquitetura e fluxo de dados |
| [02_stack.md](02_stack.md) | Stack tecnológica e requisitos |
| [03_fluxo_autenticacao.md](03_fluxo_autenticacao.md) | Login duplo RSA/MD5/AES, keepalive, updateToken |
| [04_endpoints_defense.md](04_endpoints_defense.md) | Endpoints internos (a nossa API → Defense IA) |
| [05_endpoints_api.md](05_endpoints_api.md) | Endpoints externos (equipe YOLO → a nossa API) |
| [06_streaming_video.md](06_streaming_video.md) | RTSP, montagem da URL e proxy MJPEG |
| [07_multicamera_http2.md](07_multicamera_http2.md) | Várias câmeras numa aba via HTTP/2 (Caddy) |
| [08_gpu_decode.md](08_gpu_decode.md) | Decode por GPU (NVDEC) e escala para dezenas de câmeras |
| [09_mapa_paginas_manual.md](09_mapa_paginas_manual.md) | **Mapa cronológico**: páginas do manual + campos da API por etapa |
| [10_consumo_rtsp.md](10_consumo_rtsp.md) | **Consumir RTSP corretamente** (token de uso único) + código p/ IA/VLC |

> Fonte primária: manual **"Defense API 3.2"** (Intelbras / VMS platform),
> seções 3.3.5 (criptografia), 4.2–4.3 (conexão e login) e 5.3 / 6.2.4.2 (vídeo).
