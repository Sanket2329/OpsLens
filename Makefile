.PHONY: up down logs test migrate shell lint

# ── Docker ────────────────────────────────────────────────────────────────────

up:
	docker compose up -d

fresh:
	docker compose down -v
	docker compose up -d

down:
	docker compose down

down-v:
	docker compose down -v

logs:
	docker compose logs -f api

build:
	docker compose build api

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	cd backend && source .venv/bin/activate && alembic upgrade head

migration:
	cd backend && source .venv/bin/activate && alembic revision --autogenerate -m "$(msg)"

# ── Tests ─────────────────────────────────────────────────────────────────────

test:
	cd backend && source .venv/bin/activate && python -m pytest tests/ -v

test-unit:
	cd backend && source .venv/bin/activate && python -m pytest tests/unit/ -v

test-integration:
	cd backend && source .venv/bin/activate && python -m pytest tests/integration/ -v

# ── Development ───────────────────────────────────────────────────────────────

dev:
	cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

shell:
	cd backend && source .venv/bin/activate && python

install:
	cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# ── Health ────────────────────────────────────────────────────────────────────

health:
	curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
