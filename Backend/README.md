# Backend - Advanced, Config-Driven Chatbot API

This backend exposes three layers of capability:
- v1: Original endpoint in `main.py` (/process-user-query/)
- v2: Structured router in `app_route.py` (/v2/process-user-query/)
- v3: Fully dynamic, config-driven router in `dynamic_router.py` (/v3/route)

## Highlights
- Centralized settings in `config.py`, merging `.env` and `app.royete`.
- Intent registry and handlers in `core/` with config `config/intents.json`.
- Optional middlewares for request IDs and timing metrics.
- LangChain-based general chat and SAP services integration.

## Quickstart

1) Create/activate venv

```powershell
python -m venv .\venv
.\.venv\Scripts\Activate.ps1
```

2) Install deps

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

3) Set env vars in `.env` (required at import time by SAP services):

```
SAP_BASE_URL=https://your-sap-host/sap/opu/odata/sap
SAP_USERNAME=your-user
SAP_PASSWORD=your-pass
SAP_CLIENT=100
OPENAI_API_KEY=your-key
```

4) Run

```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

5) Explore docs at http://127.0.0.1:8000/docs

- v1: POST /process-user-query/
- v2: POST /v2/process-user-query/
- v3: POST /v3/route

### v3 sample payloads

- Natural language (router will auto-detect):

```json
{
  "user_query": "Create telephone address for plant 1001 with number +1 222 333"
}
```

- Explicit (no NLP):

```json
{
  "intent": "CreateTelephoneAddress",
  "entities": { "PLANT": "1001", "TELEPHONE": "+1 222 333" }
}
```

## Notes
- If you see import errors for `dotenv`, ensure you installed `python-dotenv` (not `dotenv`).
- FastAPI >= 0.100 requires Pydantic v2. This repo sets `pydantic>=2`.
- `langchain-openai` is required for `from langchain_openai import ChatOpenAI`.
- `PyYAML` is needed to parse `app.royete`.

## Structure
- `config.py` — settings, logging and CORS helpers
- `app_route.py` — v2 router
- `dynamic_router.py` — v3 router (fully dynamic)
- `core/intent_registry.py` — registry & dispatcher
- `core/handlers/` — modular handlers for telephone, postal, general chat
- `config/intents.json` — intent-to-handler mapping and required fields
- `middleware/` — request-id and timing middlewares
- `services/` — SAP & NLP services (existing)
