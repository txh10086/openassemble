# Valve Assembly Demo

This repository contains a FastAPI demonstration for decomposing valve assembly tasks and an optional RAG knowledge base module.

## Features

- SSE streaming of decomposition progress
- Excel and JSON export
- Knowledge base for document uploads and querying
- Dashboard style front‑end with interactive diagrams

## Requirements

- Python 3.8+
- `OPENAI_API_KEY` environment variable with a valid OpenAI compatible API key
- Optional HTTP basic auth credentials via `APP_USERNAME` and `APP_PASSWORD`

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

## Running

Start the main decomposition server:

```bash
python app.py
```

Optional: start the RAG knowledge base service:

```bash
python backend/rag/app.py
```

Both services start on port `8001` and `8000` respectively.
Use the username and password set in `APP_USERNAME` and `APP_PASSWORD` when accessing protected endpoints.

## License

This project is released under the MIT License. See [LICENSE](LICENSE) for details.
