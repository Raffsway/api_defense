# `app/defense_client.py` — `DefenseManager`

## Responsabilidade
Manter uma **sessão autenticada** com o Defense IA e expor operações de alto
nível, escondendo criptografia, headers e gestão de token.

## Construtor
`DefenseManager(crypto=None)` — injeta opcionalmente um `DefenseCrypto` (default
cria um). Cria um `httpx.AsyncClient` com `base_url`, timeout e `verify` vindos
de `Settings`.

## Estado
`token`, `user_id`, `aes_key`, `aes_vector`, `_temp4` (p/ updateToken),
`_keepalive_task`, `_login_lock` (evita logins concorrentes).

## Propriedade
- `is_authenticated -> bool`

## Métodos públicos

### `async login()`
Executa o fluxo duplo sob `_login_lock`:
1. `_first_authorize()` → `realm`, `randomKey` (HTTP 401 é normal).
2. `_second_authorize()` → `token`, `userId` e decripta `secretKey`/`secretVector`.

### `start_keepalive()` / `async stop_keepalive()`
Inicia/cancela a `asyncio.Task` de heartbeat em background.

### `async start_video(channel_id, stream_type=None) -> str`
Chama `MTS.Video.StartVideo` e devolve a **URL RTSP completa**
(`url + "?token=" + token`). Usa `_post_with_relogin` (re-login automático).

### `async list_cameras(online_only=False) -> dict`
Lista as câmeras agrupadas por unidade. Combina `GET /tree/deviceOrg` (mapa
código→nome da unidade) com `POST /tree/devices` (dispositivos + canais com
`channelCode`/`channelName`), filtra canais encoder (`channelType == "1"`) e
agrupa por `orgCode`. Retorna `{"total", "units": [{code, name, cameras: [...]}]}`.

### `async close()`
Para o keepalive e fecha o cliente httpx.

## Métodos internos

| Método | Função |
|---|---|
| `_first_authorize()` | 1ª etapa do login |
| `_second_authorize(realm, random_key)` | 2ª etapa (assinatura + RSA) |
| `_keepalive_loop()` | Laço: heartbeat a cada `keepalive_interval`; a cada N renova o token; em erro tenta re-login |
| `_keepalive_once()` | `PUT /keepalive`; exige `code == "1000"` |
| `_update_token()` | `POST /updateToken` com `md5(temp4:token)` |
| `_auth_headers()` | Monta `X-Subject-Token` + `Content-Type` |
| `_request_with_relogin(method, path, json)` | Requisição autenticada (GET/POST); em `401` ou `7001/7002` refaz login e tenta 1x |
| `_post_with_relogin(path, body)` | Atalho POST sobre `_request_with_relogin` |

## Tratamento de erros
- `DefenseError` — erro de negócio (corpo inesperado, `code != 1000`, sem token).
- `_safe_json()` — converte resposta não-JSON em `DefenseError` clara.
- O laço de keepalive **nunca morre**: captura exceções e tenta re-login.

## Decisões de projeto
- **Injeção de `DefenseCrypto`** facilita testes.
- **Re-login idempotente** com `_login_lock` evita corrida de múltiplos logins.
- Falha ao decriptar AES é **não fatal** (só afeta senhas/MQ, não o vídeo).
