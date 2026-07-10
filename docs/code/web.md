# `app/web.py` — `WebApplication`

## Responsabilidade
Orquestrar os componentes (`DefenseManager` + `CameraHub`), definir o ciclo de
vida da aplicação e expor os endpoints HTTP. É uma **API pura** (sem frontend);
a única interface é o Swagger em `/docs`.

## Construtor
`WebApplication()` cria `self.manager` (`DefenseManager`), `self.hub`
(`CameraHub`, captura compartilhada) e monta `self.app` (instância FastAPI) via
`_build_app()`.

## Ciclo de vida (`_lifespan`)
- **Startup:** `manager.login()` + `manager.start_keepalive()`. Se o login
  falhar, **não derruba** o servidor (loga e tenta sob demanda).
- **Shutdown:** `hub.shutdown()` (para as capturas) + `manager.close()`.

## Rotas registradas (`_register_routes`)

| Método/rota | Função |
|---|---|
| `GET /` | Redireciona para `/docs` (fora do schema) |
| `GET /health` | Status: versão, base_url, autenticado, userId, streams ativos |
| `GET /api/v1/cameras` | Lista câmeras por unidade |
| `GET /api/v1/cameras/{channel_id}/rtsp` | JSON `{channel_id, rtsp_url}` |
| `GET /api/v1/cameras/{channel_id}/stream` | `StreamingResponse` MJPEG via `hub.mjpeg_stream` (captura compartilhada) |

> O `/stream` **não** chama `_safe_start_video`: a obtenção da URL RTSP acontece
> dentro do `CameraStream` (thread), permitindo reconexão automática. Erros de
> câmera aparecem como timeout do 1º frame (stream encerra), não como 5xx.

## Helper de erros (`_safe_start_video`)
Centraliza `manager.start_video()` e mapeia exceções para HTTP:

| Exceção | HTTP |
|---|---|
| `DefenseError` (erro de negócio) | `502` |
| `httpx.RequestError` (inacessível/timeout) | `503` |
| Qualquer outra | `500` |

## Factory
`create_app() -> FastAPI` — permite `uvicorn app.web:create_app --factory`.

## Decisões de projeto
- **Classe** em vez de globais soltas: estado (manager/streamer) encapsulado,
  fácil de instanciar em testes.
- Dashboard servido como arquivo estático (sem template engine) — simples e leve.
- Mapeamento explícito de erros dá respostas claras à equipe cliente.
