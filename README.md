# Trivago Scraper API

API em FastAPI para consultar precos de hoteis indexados no Trivago, retornando:

- nomeDoHotel (string)
- local (string)
- precos (dicionario indexador -> preco)

Exemplo de precos:

```json
{
  "MaxMilhas": 1138.48,
  "Trip.com": 1799
}
```

## Stack

- Python 3.11+
- FastAPI
- HTTPX + BeautifulSoup (coleta primaria)
- Playwright (fallback para pagina dinamica/bloqueio)
- Enriquecimento opcional por pagina de detalhe para tentar extrair indexadores

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Execucao

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Execucao com Docker

### 1) Build da imagem

```bash
docker build -t trivago-api:latest .
```

### 2) Subir container

```bash
docker run --rm -d \
  --name trivago-api \
  -p 8001:8000 \
  --env-file .env.example \
  trivago-api:latest
```

### 3) Ver logs (opcional)

```bash
docker logs -f trivago-api
```

### 4) Parar container

```bash
docker stop trivago-api
```

### Exemplos de chamadas cURL

Healthcheck:

```bash
curl -X GET http://localhost:8000/health
```

Busca de hoteis:

```bash
curl -X POST http://localhost:8000/api/v1/hoteis/buscar \
  -H "Content-Type: application/json" \
  -d '{
    "destino": "Recife",
    "dataCheckin": "2026-05-10",
    "dataCheckout": "2026-05-12",
    "adultos": 2,
    "criancas": 0,
    "limite_resultados": 5
  }'
```

Documentacao interativa:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Endpoints

### GET /health

Verifica se a API esta online.

Resposta 200:

```json
{
  "status": "ok",
  "scraper_available": true,
  "timestamp": "2026-04-20T16:00:00Z"
}
```

### POST /api/v1/hoteis/buscar

Busca hoteis por destino e datas.

Body:

```json
{
  "destino": "Recife",
  "dataCheckin": "2026-05-10",
  "dataCheckout": "2026-05-12",
  "adultos": 2,
  "criancas": 0,
  "limite_resultados": 20
}
```

Resposta 200 (success ou partial):

```json
{
  "status": "success",
  "timestamp": "2026-04-20T16:00:00Z",
  "quantidade_resultados": 2,
  "hoteis": [
    {
      "nomeDoHotel": "Hotel Atlante Plaza",
      "local": "Boa Viagem, Recife",
      "precos": {
        "MaxMilhas": 1138.48,
        "Trip.com": 1799
      }
    }
  ],
  "avisos": []
}
```

### Codigos de erro

- 400: payload invalido (datas, tipos, limites)
- 429: limite de requisicoes por minuto
- 503: coleta indisponivel no momento (bloqueio, timeout, parse vazio)

## Variaveis de ambiente

Copie `.env.example` e ajuste conforme necessidade.

- TRIVAGO_BASE_URL
- REQUEST_TIMEOUT_SECONDS
- RETRY_ATTEMPTS
- RETRY_BACKOFF_SECONDS
- USE_PLAYWRIGHT_FALLBACK
- PLAYWRIGHT_TIMEOUT_MS
- RATE_LIMIT_PER_MINUTE
- ENRICH_INDEXERS_ENABLED
- MAX_ENRICH_HOTELS

## Como os indexadores sao extraidos

- O scraper extrai a listagem inicial (nome, local e preco campeao do Trivago).
- Em seguida, tenta enriquecer cada hotel visitando a pagina de detalhe para encontrar
  pares indexador -> preco (ex.: Booking.com, Trip.com, Expedia).
- Segunda estrategia: quando a pagina de detalhe nao traz parceiros no HTML estatico,
  o scraper usa Playwright para abrir o fluxo "Ver preços" e tentar capturar parceiros
  renderizados dinamicamente.
- Quando nao houver indexadores adicionais disponiveis no HTML, o resultado mantem
  ao menos o preco `Trivago`.

Controles dessa estrategia:

- `PLAYWRIGHT_DYNAMIC_ENRICHMENT_ENABLED` ativa/desativa o fallback dinamico.
- `MAX_PLAYWRIGHT_ENRICH_HOTELS` limita quantos hoteis por requisicao usam esse fallback.

## Testes

```bash
pytest -q
```

## Observacoes importantes

- O Trivago pode mudar layout e quebrar parsing.
- O site pode aplicar mecanismos anti-bot e retornar 403/429.
- A API pode retornar `status=partial` com avisos quando a coleta for parcial.
- Use com responsabilidade e respeitando robots/termos da fonte.
