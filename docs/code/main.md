# `main.py` — Entrypoint

## Responsabilidade
Ponto de entrada da aplicação. Instancia a `WebApplication`, expõe o objeto
`app` (FastAPI) para o uvicorn e oferece um `main()` para execução direta.

## Conteúdo
```python
web_application = WebApplication()
app = web_application.app          # consumido por: uvicorn main:app

def main() -> None:
    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port)

if __name__ == "__main__":
    main()
```

## Formas de executar
```bash
python main.py                                  # usa API_HOST/API_PORT do .env
uvicorn main:app --host 0.0.0.0 --port 8000     # controle manual
uvicorn app.web:create_app --factory            # via factory
```

## Acessos após subir
- Painel: `http://<host>:<port>/`
- Swagger: `http://<host>:<port>/docs`
- Health: `http://<host>:<port>/health`

## Decisão de projeto
`app` é exposto no nível do módulo (e não dentro de `main()`) porque o uvicorn,
ao recarregar/importar `main:app`, precisa do objeto no escopo do módulo.
