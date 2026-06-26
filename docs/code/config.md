# `app/config.py` — `Settings`

## Responsabilidade
Centralizar toda a configuração da aplicação, lida **uma única vez** do
ambiente / arquivo `.env`.

## Como funciona
- No import, `load_dotenv()` carrega o `.env` da raiz do projeto
  (`Path(__file__).parent.parent / ".env"`).
- A classe `Settings` é um `@dataclass(frozen=True)` (imutável). Cada campo usa
  `field(default_factory=...)` para ler a variável de ambiente correspondente.
- Uma instância única `settings` é criada no fim do módulo e importada pelos
  demais módulos.

## Campos principais

| Campo | Variável `.env` | Default | Descrição |
|---|---|---|---|
| `defense_ip` | `DEFENSE_IP` | `192.168.1.1` | IP do Defense IA |
| `defense_port` | `DEFENSE_PORT` | `80` | Porta do Defense IA |
| `defense_scheme` | `DEFENSE_SCHEME` | `http` | `http`/`https` |
| `defense_username` | `DEFENSE_USERNAME` | `system` | Usuário |
| `defense_password` | `DEFENSE_PASSWORD` | *(vazio)* | Senha |
| `client_mac` | `DEFENSE_CLIENT_MAC` | *(auto)* | MAC do "cliente". **Vazio = detecta o MAC da máquina** via `uuid.getnode()` (`_auto_mac()`). Nativo: MAC real da NIC; em Docker: MAC do container. Defina explicitamente se quiser um valor fixo/estável. |
| `client_type` | `DEFENSE_CLIENT_TYPE` | `WINPC_V2` | Tipo de cliente |
| `verify_tls` | `DEFENSE_VERIFY_TLS` | `true` | Verificar TLS |
| `keepalive_interval` | `DEFENSE_KEEPALIVE_INTERVAL` | `22` | s entre heartbeats |
| `update_token_every_n_heartbeats` | `DEFENSE_UPDATE_TOKEN_EVERY` | `60` | heartbeats até renovar token |
| `http_timeout` | `DEFENSE_HTTP_TIMEOUT` | `15` | timeout httpx (s) |
| `default_stream_type` | `DEFENSE_DEFAULT_STREAM_TYPE` | `1` | stream padrão |
| `stream_fps_limit` | `STREAM_FPS_LIMIT` | `0` | limite de FPS (0=off) |
| `stream_jpeg_quality` | `STREAM_JPEG_QUALITY` | `80` | qualidade JPEG |
| `api_host` | `API_HOST` | `0.0.0.0` | host da nossa API |
| `api_port` | `API_PORT` | `8000` | porta da nossa API |

## Propriedade computada
- `defense_base_url` → `"{scheme}://{ip}:{port}"`.

## Decisões de projeto
- **Imutável** (`frozen=True`): evita mudanças acidentais em runtime.
- **`default_factory`**: garante que o `.env` (carregado antes) seja lido na
  construção da instância, mantendo defaults seguros se a variável faltar.
