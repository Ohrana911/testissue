# Room sensor readings service

A small in-memory HTTP service that accepts room sensor readings and returns
the latest reading of each sensor. Built with FastAPI. All data is fictional.

## Setup, run, test

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                  # install dependencies
uv run uvicorn app.main:app --reload     # run the service on http://127.0.0.1:8000
uv run pytest -v                         # run the tests
```

Interactive API docs (Swagger UI) are available at http://127.0.0.1:8000/docs.

## API

### POST /readings

| Case | Response |
|---|---|
| New `event_id` | `201` `{"status": "accepted"}` |
| Same `event_id` with the same `sensor_id`, `value`, `observed_at` | `200` `{"status": "duplicate"}`, state unchanged |
| Same `event_id` with different data | `409`, state unchanged |
| Invalid request | `422` with a JSON list of errors (field and message), nothing is stored |

### GET /sensors/{sensor_id}/latest

`200` with the latest reading, or `404` with a JSON error if the sensor has no data.
"Latest" is decided by `observed_at`, not by arrival time. If two events of one
sensor have the same `observed_at`, the one accepted first stays the latest.

## Example requests

```bash
curl -X POST http://127.0.0.1:8000/readings \
  -H "Content-Type: application/json" \
  -d '{"event_id": "event-001", "sensor_id": "room-01-temperature", "value": 22.4, "observed_at": "2026-10-12T10:00:00Z"}'

curl http://127.0.0.1:8000/sensors/room-01-temperature/latest
```

## Design notes and assumptions

- `app/models.py`: request validation (Pydantic). Unknown fields are rejected;
  `value` must be a finite JSON number (not a string, not a boolean);
  `observed_at` must match `YYYY-MM-DDTHH:MM:SS[.fraction]Z` exactly and be a real date.
  It is parsed into an aware datetime, so `10:00:00Z` and `10:00:00.000Z` are the same moment.
- `app/storage.py`: in-memory state. `events` (event_id -> reading) is used for
  duplicate/conflict checks and keeps every accepted reading, including old ones.
  `latest` (sensor_id -> reading) is replaced only if `observed_at` is strictly greater.
  `22` and `22.0` compare as equal.
- `app/main.py`: HTTP layer. A custom 422 handler returns only the field and message
  of each error: the default handler echoes the raw input, which fails to serialize
  for `NaN`/`Infinity` and caused HTTP 500 (found by a test).
- Assumption: `event_id` and `sensor_id` made only of whitespace are rejected.
  Leading/trailing spaces in an otherwise non-empty id are kept as sent.
- All access to the state goes through a lock, so the store is thread-safe.

## Limitations

- State lives in memory of one process and is lost on restart.
- With several uvicorn workers every worker would have its own state.
- No authentication, persistence, pagination, or limits on the number of stored readings.

## Time spent

About 4 hours. Possible improvements: a limit on the number of stored readings. Memory grows with every accepted event, and persistent storage.

## AI usage

I used an AI assistant (Claude) for: choosing the framework, a project skeleton,
explanations of Pydantic validators and the Python concepts used, drafts of
`storage.py`, `main.py` and the tests, and a review of my `models.py`.
I checked the result by: reading and explaining each part, running the full
scenario from the task manually via Swagger UI (`/docs`), and the automated tests
(`uv run pytest`). The tests found one real bug (HTTP 500 instead of 422 for
`NaN`/`Infinity`), which was then fixed with a custom validation error handler.
