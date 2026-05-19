# YT Downloader

Minimal web UI for downloading YouTube videos as MP4.

## Docker

```bash
docker compose up --build
```

Open http://localhost:8000

## Local

```bash
uv sync
uv run uvicorn app:app --reload
```

Or: `make install && make run`
