# Document Processor

Asynchronous document-processing service: accepts a job via `POST /jobs`,
processes it in the background, and exposes status via `GET /jobs/{id}`.

> **Status: work in progress.** This commit sets up the project scaffold and
> tooling. The domain model, API, worker, and observability are added in
> subsequent commits — see the commit history for progress.

## Stack

FastAPI, Pydantic v2, httpx, structlog, prometheus-client, pytest.

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -e ".[dev]"
```

## Development commands

```bash
ruff check .      # lint
mypy app          # type check
pytest            # tests
```
