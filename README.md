# Document Processor

An asynchronous document-processing service. A client submits a document
URL and an operation; the work happens off the HTTP request path in a
background worker, and the client polls a job-status endpoint for the
result.

Built as a take-home exercise, with an emphasis on clean boundaries,
correct concurrency behavior (idempotency, retries, state machine), and
honest documentation over feature breadth.

## Contents

- [Architecture](#architecture)
- [Getting started](#getting-started)
- [API](#api)
- [Configuration](#configuration)
- [Testing](#testing)
- [Assumptions](#assumptions)
- [Trade-offs and known gaps](#trade-offs-and-known-gaps)
- [Path to a durable deployment](#path-to-a-durable-deployment)
- [Project layout](#project-layout)

## Architecture

Ports-and-adapters: the API and the background worker are two entry points
into the same domain/service core. Neither the domain nor the application
layer imports FastAPI, httpx, or any storage library directly — they
depend on `Protocol` interfaces, which adapters implement.

```
 HTTP layer                 Background worker
 (FastAPI routers)          (asyncio task, started in the app lifespan)
       |                            |
       v                            v
                JobService                     <- orchestration
        submit() / get(), idempotency
                    |
     +--------------+-----------------+
     |              |                 |
JobRepository    JobQueue      DocumentFetcher / processor registry
 (Protocol)      (Protocol)     (Protocol / Operation -> callable)
     |              |                 |
InMemoryJobRepository     InMemoryJobQueue     HttpDocumentFetcher (httpx)
(swap for Postgres/etc.)  (swap for Redis/SQS)  word_count / sha256 / metadata
```

- **`JobService`** owns submission and idempotency; it's the only thing
  that enqueues work.
- **`Worker`** owns the processing loop and the retry decision, driven by
  whether a failure is `TransientProcessingError` or
  `PermanentProcessingError`.
- **`Job`** (the domain entity) owns its own state machine
  (`queued → running → succeeded|failed`, with `running → queued` for
  retries) and rejects illegal transitions, so a job can never get stuck
  in `running`.

## Getting started

Requires Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The API is then available at `http://127.0.0.1:8000` (interactive docs at
`/docs`).

### Example requests

```bash
# Submit a job
curl -i -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-1" \
  -d '{"document_url": "https://example.com/some.txt", "operation": "word_count"}'

# -> 202 Accepted, Location: /jobs/<id>

# Poll for the result
curl http://127.0.0.1:8000/jobs/<id>

# Liveness / readiness / metrics
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
curl http://127.0.0.1:8000/metrics
```

### Docker (optional)

```bash
docker build -t document-processor .
docker run -p 8000:8000 document-processor
```

## API

| Method | Path          | Description                                              |
|--------|---------------|-----------------------------------------------------------|
| POST   | `/jobs`       | Submit a document for processing. Returns 202 (new job) or 200 (idempotent replay). |
| GET    | `/jobs/{id}`  | Get job status, attempts, result, and error. 404 if unknown. |
| GET    | `/healthz`    | Liveness: 200 whenever the process is up.                 |
| GET    | `/readyz`     | Readiness: 503 until the worker pool has started and resynced; 503 again while shutting down. |
| GET    | `/metrics`    | Prometheus exposition format.                              |

**POST /jobs** request body:

```json
{ "document_url": "https://example.com/doc.txt", "operation": "word_count" }
```

`operation` is one of `word_count`, `sha256`, `metadata`. `Idempotency-Key`
is an optional request header.

**GET /jobs/{id}** response:

```json
{
  "id": "…", "status": "succeeded", "operation": "word_count",
  "document_url": "…", "attempts": 1,
  "result": { "word_count": 42 }, "error": null,
  "created_at": "…", "updated_at": "…"
}
```

## Configuration

Environment variables (prefix `APP_`), also loadable from a local `.env`:

| Variable               | Default | Description                              |
|------------------------|---------|-------------------------------------------|
| `APP_LOG_LEVEL`        | `INFO`  | Log level for structured (JSON) logs.      |
| `APP_WORKER_CONCURRENCY` | `2`   | Number of concurrent worker tasks.         |

## Testing

```bash
ruff check .    # lint
mypy app        # type check
pytest          # unit + integration tests
```

The suite includes unit tests for the domain state machine, idempotency
(including a 20-way concurrent-submission test), retry policy, processors,
and the worker; plus integration tests that drive the real FastAPI app
(API → service → worker → adapters) with `respx` mocking the document
server, covering the happy path, idempotent resubmission, retry-then-
succeed, and retry exhaustion.

## Assumptions

Several things were intentionally left ambiguous in the brief. Here's what
was assumed, and why:

- **Retry count**: "retry up to three times" = 1 initial attempt + 3
  retries = 4 attempts total (`Job.max_attempts = 4`).
- **Idempotency-Key scope**: global, not scoped per client. The key plus
  the request payload (`document_url` + `operation`) determines whether a
  resubmission is a replay (same payload → same job returned) or a
  conflict (different payload → `409 Conflict`). No TTL/eviction is
  implemented — see trade-offs.
- **Idempotent replay status code**: a brand-new job returns `202
  Accepted`; returning the same job for a repeated key returns `200 OK`,
  since no new resource was created.
- **Error classification**: timeouts, connection errors, HTTP 408/429/5xx
  are treated as transient (retried); HTTP 4xx (other than 408/429) and
  oversized bodies are treated as permanent (fail immediately).
- **Supported operations**: `word_count`, `sha256`, `metadata` — chosen to
  demonstrate the processor registry extension point, not for their own
  sake.
- **Document size/timeout limits**: a streamed 10 MB cap and a 10s request
  timeout, both hardcoded in `HttpDocumentFetcher` (not yet exposed via
  settings).

## Trade-offs and known gaps

Being upfront about what an interview timebox doesn't cover:

- **In-memory storage**: all jobs and the queue live in process memory.
  Restarting the process loses everything except what `Worker.resync()`
  can recover from the repository — and since the repository is also
  in-memory, a real restart loses state. This is acceptable for the
  timebox; see below for how to make it durable.
- **Single process**: the queue is an `asyncio.Queue`, so this doesn't
  scale beyond one process/host as-is.
- **No authentication/authorization**: every caller can submit and read
  any job.
- **No SSRF protection**: `HttpDocumentFetcher` will happily fetch
  internal/loopback addresses if given a URL for one. A production version
  should resolve and block private IP ranges before connecting.
- **At-least-once processing**: a crash between a successful fetch/process
  and persisting the result could cause a job to be retried unnecessarily.
  Processors here are idempotent (pure functions of the document bytes),
  so this is safe in practice, but a processor with side effects would
  need its own idempotency handling.
- **No idempotency-key TTL**: keys are kept forever (bounded only by how
  long the process runs); a real deployment would expire them after some
  window.
- **No job cancellation or listing endpoint**: out of scope for the
  required behavior.

## Path to a durable deployment

The point of the ports/adapters split is that none of this requires
touching `JobService` or `Worker`:

- **Storage**: implement `JobRepository` (see `app/ports/repository.py`)
  against Postgres. Use a unique constraint on `idempotency_key` instead
  of the in-process `asyncio.Lock` for the atomic check-and-insert, and
  `SELECT ... FOR UPDATE SKIP LOCKED` (or equivalent) for claiming jobs if
  you run multiple worker processes.
- **Queue**: implement `JobQueue` (see `app/ports/queue.py`) against
  Redis, SQS, or similar, so the queue survives process restarts and can
  be shared across worker instances.
- **Wiring**: swap the adapter construction in `app/main.py`'s
  `create_app()` — the rest of the application is unaffected.

## Future work

Rate limiting, idempotency-key TTL/eviction, a dead-letter queue for jobs
that exhaust retries, distributed tracing, authentication, and a job
cancellation endpoint.

## Project layout

```
app/
  api/            FastAPI routers, request/response schemas, health, metrics
  domain/         Job entity, state machine, errors — no framework deps
  services/       JobService (orchestration), Worker, retry policy
  ports/          Protocol interfaces: JobRepository, JobQueue, DocumentFetcher
  adapters/       In-memory repository/queue, httpx-based fetcher
  processors/     word_count, sha256, metadata + the operation registry
  observability/  structlog config, Prometheus metrics, request-id middleware
  config.py       Settings (env-driven)
  main.py         Composition root: wires adapters and the worker lifespan
tests/
  unit/           Fast, isolated tests per component
  integration/    Full-stack tests through the real FastAPI app
```
