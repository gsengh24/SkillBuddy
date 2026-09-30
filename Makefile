# Developer entry points. Everything runs inside the Compose containers, so the only
# host requirements are Docker and make. Run `make help` for the list.

COMPOSE ?= docker compose
BACKEND  = $(COMPOSE) run --rm --no-deps api
WEB      = $(COMPOSE) run --rm --no-deps web

.DEFAULT_GOAL := help
.PHONY: help up down logs ps migrate downgrade revision test lint format psql

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Build and start the whole stack; waits until every service is healthy
	$(COMPOSE) up --build --detach --wait

down: ## Stop the stack (data volumes are kept; add `-v` manually to wipe them)
	$(COMPOSE) down

logs: ## Follow logs (all services, or one: make logs s=api)
	$(COMPOSE) logs --follow $(s)

ps: ## Show service status and health
	$(COMPOSE) ps

migrate: ## Apply migrations (default head; or make migrate rev=<revision>)
	$(COMPOSE) run --rm migrate alembic upgrade $(or $(rev),head)

downgrade: ## Revert migrations (default one step; or make downgrade rev=<revision|base>)
	$(COMPOSE) run --rm migrate alembic downgrade $(or $(rev),-1)

revision: ## Autogenerate a migration from model changes: make revision m="add requests table"
	@test -n "$(m)" || (echo 'usage: make revision m="short description"' && exit 1)
	$(COMPOSE) run --rm migrate alembic revision --autogenerate -m "$(m)"

test: ## Run the backend test suite (unit + integration against real Postgres/Redis)
	$(COMPOSE) up --detach --wait db redis
	$(BACKEND) pytest --cov --cov-report=term-missing

lint: ## Lint, format-check and type-check backend and frontend
	$(BACKEND) sh -c 'ruff check . && ruff format --check . && mypy'
	$(WEB) sh -c 'npm run lint && npm run typecheck && npm run format:check'

format: ## Auto-format and auto-fix backend and frontend
	$(BACKEND) sh -c 'ruff format . && ruff check --fix .'
	$(WEB) sh -c 'npm run format && npm run lint:fix'

psql: ## Open a psql shell on the local database
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'
