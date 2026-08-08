# ============================================================
# RAG Agent Platform — Makefile
# ============================================================

.PHONY: help
help:
	@echo "📋 RAG Agent Platform — Available Commands"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  make setup          Install all dependencies"
	@echo "  make dev            Run FastAPI with hot-reload (local)"
	@echo "  make docker-up      Start all Docker services"
	@echo "  make docker-down    Stop all Docker services"
	@echo "  make docker-build   Build backend with cache"
	@echo "  make docker-rebuild Rebuild backend (no cache)"
	@echo "  make docker-restart Restart backend container"
	@echo "  make test           Run pytest with coverage"
	@echo "  make lint           Run ruff linter"
	@echo "  make format         Run ruff formatter"
	@echo "  make type-check     Run mypy type checker"
	@echo "  make migrate        Run Alembic migrations"
	@echo "  make docker-clean   Clean Docker cache"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Setup ────────────────────────────────────────────────────
.PHONY: setup
setup:
	@echo "📦 Installing dependencies..."
	uv sync --extra dev --extra monitoring --extra frontend --extra data --extra llm
	@echo "✅ Dependencies installed."
	uv run pre-commit install
	@echo "✅ Pre-commit hooks installed."

# ─── Development ──────────────────────────────────────────────
.PHONY: dev
dev:
	@echo "🚀 Starting FastAPI dev server on http://localhost:8000"
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# ─── Docker ────────────────────────────────────────────────────
.PHONY: docker-up
docker-up:
	@echo "🐳 Starting Docker services..."
	export DOCKER_BUILDKIT=1 && docker-compose up -d
	@echo "✅ Services started."
	@echo "   Backend:    http://localhost:8080"
	@echo "   Frontend:   http://localhost:8081"
	@echo "   PostgreSQL: localhost:5433 (user: postgres, password: postgres)"
	@echo "   Redis:      localhost:6380"
	@echo "   Grafana:    http://localhost:8082 (admin/admin)"

.PHONY: docker-down
docker-down:
	@echo "🛑 Stopping Docker services..."
	docker-compose down
	@echo "✅ Services stopped."

.PHONY: docker-build
docker-build:
	@echo "🔨 Building backend (using cache)..."
	export DOCKER_BUILDKIT=1 && docker-compose build backend
	@echo "✅ Build complete."

.PHONY: docker-rebuild
docker-rebuild:
	@echo "🔨 Rebuilding backend (no cache)..."
	export DOCKER_BUILDKIT=1 && docker-compose build --no-cache backend
	@echo "✅ Rebuild complete."

.PHONY: docker-restart
docker-restart:
	@echo "🔄 Restarting backend..."
	docker-compose restart backend
	@echo "✅ Backend restarted."

.PHONY: docker-logs
docker-logs:
	docker-compose logs -f

.PHONY: docker-clean
docker-clean:
	@echo "🧹 Cleaning Docker cache..."
	docker system prune -a -f
	docker builder prune -f
	@echo "✅ Clean complete."

# ─── Testing ──────────────────────────────────────────────────
.PHONY: test
test:
	@echo "🧪 Running tests..."
	uv run pytest tests/ -v --cov=app --cov-report=term-missing

# ─── Linting ──────────────────────────────────────────────────
.PHONY: lint
lint:
	@echo "🔍 Running ruff linter..."
	uv run ruff check app tests

.PHONY: format
format:
	@echo "🎨 Running ruff formatter..."
	uv run ruff format app tests

.PHONY: type-check
type-check:
	@echo "📋 Running mypy type checker..."
	uv run mypy app

# ─── Database ─────────────────────────────────────────────────
.PHONY: migrate
migrate:
	@echo "📊 Running migrations..."
	uv run alembic upgrade head
	@echo "✅ Migrations complete."

.PHONY: migrate-create
migrate-create:
	@if [ -z "$(MSG)" ]; then \
		echo "❌ Please provide a migration message: make migrate-create MSG='add table'"; \
		exit 1; \
	fi
	@echo "📝 Creating migration: $(MSG)"
	uv run alembic revision --autogenerate -m "$(MSG)"

# ─── Cleanup ──────────────────────────────────────────────────
.PHONY: clean
clean:
	@echo "🧹 Cleaning cache..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov build dist 2>/dev/null || true
	@echo "✅ Clean complete."

# ─── Default ──────────────────────────────────────────────────
.DEFAULT_GOAL := help
