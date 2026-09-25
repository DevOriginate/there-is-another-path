# There Is Another Path — Path Engine V1

Deterministic, explainable recommendation engine for **The Path Finder** MVP.

## Status

**Runnable MVP engine.** The engine accepts the 26-question assessment, creates a user vector, scores 27 paths, applies hard gates and penalties, returns a diversified Top 3, and can surface a long-term opportunity when a strong path is blocked mainly by time/urgency.

Market: **United States**  
Language: **en-US**  
Engine version: **1.0.0**  
Market calibration: **US-2026-Q3-initial**

## What is already implemented

- 26-question assessment schema
- Pydantic input validation
- trait/preference/goal vector generation
- 27-path library
- path-specific capability weights
- experience leverage logic
- time, learning, capital and risk fit
- income-urgency penalty
- prospecting mismatch penalty
- remote-work hard gate
- physical-work hard gate
- transportation/computer/internet constraints
- path-family diversification for Top 3
- long-term opportunity detection
- confidence score
- contradiction detection
- FastAPI endpoints
- CLI runner
- Docker support
- tests, including age-invariance

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Open:

- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Commercial MVP — V1.2

- Brand: **There Is Another Path**
- Product: **The Path Finder**
- Audience: United States
- Price: **US$19 one-time**
- Support: **thereisanotherp4th@gmail.com**
- Seller: **Riquelme Cordeiro de Jesus Oliveira**  
- Seller country: **Brazil**
- Refund policy: **7-day request window**
- Local persistence: SQLite
- Production persistence: PostgreSQL via `DATABASE_URL`
- `render.yaml` included for Render deployment

See `DEPLOY_RENDER.md` and `STRIPE_BRAZIL_SETUP.md`.
