# Cosmic Mycelium — Makefile
# One-command development workflow

.PHONY: help install test lint format clean docker-build docker-run

help: ## Show this help message
	@echo "🌌 Cosmic Mycelium — Development Commands"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies and pre-commit hooks
	@echo "📦 Installing dependencies..."
	pip install -e ".[dev]"
	@echo "🔧 Installing pre-commit hooks..."
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "✅ Ready! Run 'make test' to verify."

test: ## Run all tests
	@echo "🧪 Running full test suite..."
	pytest tests/ -v --cov=cosmic_mycelium --cov-report=term-missing

test-smoke: ## Run smoke tests only (fast)
	@echo "🌬️  Running smoke tests..."
	pytest tests/test_smoke.py -v

test-unit: ## Run unit tests only
	@echo "🔬 Running unit tests..."
	pytest tests/unit/ -v

test-integration: ## Run integration tests
	@echo "🔗 Running integration tests..."
	pytest tests/integration/ -v

test-physics: ## Run physics validation (energy conservation)
	@echo "⚛️  Running physics validation..."
	pytest tests/physics/ -v

benchmark: ## Run benchmarks
	@echo "📊 Running benchmarks..."
	pytest tests/ --benchmark-enable --benchmark-sort=mean

lint: ## Run linters (ruff, mypy)
	@echo "🔍 Running linters..."
	ruff check cosmic_mycelium/
	mypy cosmic_mycelium/

format: ## Auto-format code (black, isort)
	@echo "🎨 Formatting code..."
	black cosmic_mycelium/
	isort cosmic_mycelium/

format-check: ## Check code formatting without changing
	@echo "🔎 Checking code format..."
	black --check cosmic_mycelium/
	isort --check-only cosmic_mycelium/

typecheck: ## Run mypy type checking
	@echo "🔤 Type checking..."
	mypy cosmic_mycelium/

security: ## Run security audit
	@echo "🔐 Running security audit..."
	bandit -r cosmic_mycelium/ -c pyproject.toml
	pip-audit

clean: ## Clean build artifacts and cache
	@echo "🧹 Cleaning..."
	rm -rf .mypy_cache .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .eggs/
	@echo "✅ Cleaned."

docker-build: ## Build Docker image
	@echo "🐳 Building Docker image..."
	docker build -t cosmic-mycelium:dev .

docker-run: ## Run infant in Docker (dev profile)
	@echo "🚀 Running infant in Docker..."
	docker-compose -f docker-compose.dev.yml up

docker-run-cluster: ## Run cluster in Docker
	@echo "🌀 Running cluster in Docker..."
	docker-compose -f docker-compose.cluster.yml up --scale infant=3

docker-stop: ## Stop Docker containers
	@echo "🛑 Stopping Docker containers..."
	docker-compose -f docker-compose.dev.yml down
	docker-compose -f docker-compose.cluster.yml down

docs: ## Generate documentation (if Sphinx configured)
	@echo "📚 Building documentation..."
	cd docs && make html

verify: format-check lint test ## Run all verification checks
	@echo "✅ All checks passed!"

ci-local: ## Run full CI pipeline locally (slow)
	@echo "🤖 Running full CI pipeline locally..."
	make clean
	make format
	make lint
	make test
	make security
	@echo "✅ CI pipeline complete!"

## Special shortcuts

infant: ## Start infant node (dev)
	python -m cosmic_mycelium.scripts.run_infant --id dev-001

infant-prod: ## Start infant node (production profile)
	python -m cosmic_mycelium.scripts.run_infant --id prod-001 --profile prod --log-level WARNING

cluster: ## Start cluster (3 nodes)
	python -m cosmic_mycelium.scripts.run_cluster --nodes 3

physics-report: ## Generate physics validation report
	@echo "⚛️  Generating physics report..."
	python -m cosmic_mycelium.tests.physics.benchmark_physics
	@echo "📄 Report saved to reports/physics-validation.json"

## Utilities

init-db: ## Initialize vector database (Qdrant)
	@echo "🗄️  Initializing vector database..."
	docker run -p 6333:6333 qdrant/qdrant:v1.14.2

monitor: ## Start monitoring stack (Prometheus + Grafana)
	@echo "📈 Starting monitoring stack..."
	docker-compose -f docker-compose.yml up -d prometheus grafana jaeger
	@echo "🌐 Grafana: http://localhost:3000 (admin/admin)"
	@echo "📊 Prometheus: http://localhost:9090"

logs: ## Show infant logs
	@echo "📋 Infant logs:"
	docker-compose -f docker-compose.dev.yml logs -f mycelium-infant

shell: ## Open shell inside infant container
	docker-compose -f docker-compose.dev.yml exec mycelium-infant bash
