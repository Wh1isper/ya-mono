.PHONY: install
install: ## Install Python, web dependencies, and pre-commit hooks
	@echo "Creating workspace environment using uv"
	@uv sync --all-packages
	@echo "Installing web dependencies with corepack pnpm"
	@corepack pnpm install
	@uv run pre-commit install

.PHONY: install-skills
install-skills: ## Install bundled skills into ~/.agents/skills
	@echo "Installing skills into $$HOME/.agents/skills"
	@rm -rf "$$HOME/.agents/skills/agent-builder"
	@mkdir -p "$$HOME/.agents/skills/agent-builder"
	@cp -R skills/agent-builder/. "$$HOME/.agents/skills/agent-builder/"
	@mkdir -p "$$HOME/.agents/skills/agent-builder/examples"
	@cp -R examples/* "$$HOME/.agents/skills/agent-builder/examples/"
	@cp examples/.env.example "$$HOME/.agents/skills/agent-builder/examples/"

.PHONY: lint
lint: ## Lint the code
	@echo "Checking lock file consistency with pyproject.toml"
	@uv lock --locked
	@echo "Running pre-commit"
	@uv run pre-commit run -a

.PHONY: cli
cli: ## Run the CLI
	@echo "Running yaacli"
	@./scripts/sync-skills.sh
	@rm -f yaacli.log && YAACLI_PERF=1 uv run --package yaacli yaacli -v

.PHONY: run-platform
run-platform: ## Run the YA Agent Platform backend locally
	@echo "Running ya-agent-platform"
	@uv run --package ya-agent-platform ya-agent-platform serve --reload

.PHONY: platform-db-upgrade
platform-db-upgrade: ## Run YA Agent Platform DB migrations to latest
	@echo "Upgrading ya-agent-platform database"
	@uv run --package ya-agent-platform ya-agent-platform db upgrade

.PHONY: platform-db-downgrade
platform-db-downgrade: ## Roll back YA Agent Platform DB by one migration
	@echo "Downgrading ya-agent-platform database"
	@uv run --package ya-agent-platform ya-agent-platform db downgrade

.PHONY: platform-db-current
platform-db-current: ## Show current YA Agent Platform DB revision
	@echo "Showing ya-agent-platform database revision"
	@uv run --package ya-agent-platform ya-agent-platform db current

.PHONY: platform-db-history
platform-db-history: ## Show YA Agent Platform migration history
	@echo "Showing ya-agent-platform migration history"
	@uv run --package ya-agent-platform ya-agent-platform db history

.PHONY: platform-db-migrate
platform-db-migrate: ## Generate a YA Agent Platform migration (MSG required)
	@echo "Generating ya-agent-platform migration"
	@uv run --package ya-agent-platform ya-agent-platform db migrate "$(MSG)"

.PHONY: platform-infra-up
platform-infra-up: ## Start YA Agent Platform dev PostgreSQL and Redis
	@echo "Starting ya-agent-platform development infrastructure"
	@docker compose -f packages/ya-agent-platform/infra/docker-compose.dev.yml up -d

.PHONY: platform-infra-down
platform-infra-down: ## Stop YA Agent Platform dev PostgreSQL and Redis
	@echo "Stopping ya-agent-platform development infrastructure"
	@docker compose -f packages/ya-agent-platform/infra/docker-compose.dev.yml down

.PHONY: platform-infra-status
platform-infra-status: ## Show YA Agent Platform dev infrastructure status
	@echo "Showing ya-agent-platform development infrastructure status"
	@docker compose -f packages/ya-agent-platform/infra/docker-compose.dev.yml ps

.PHONY: web-install
web-install: ## Install web app dependencies with corepack pnpm
	@echo "Installing ya-agent-platform-web dependencies"
	@corepack pnpm install

.PHONY: web-dev
web-dev: ## Run the YA Agent Platform web app locally
	@echo "Running ya-agent-platform-web"
	@corepack pnpm --dir apps/ya-agent-platform-web dev

.PHONY: web-lint
web-lint: ## Run ESLint for the platform web app
	@echo "Running ya-agent-platform-web lint"
	@corepack pnpm --dir apps/ya-agent-platform-web exec eslint .

.PHONY: web-build
web-build: ## Run TypeScript and Vite build checks for the platform web app
	@echo "Running ya-agent-platform-web build"
	@corepack pnpm --dir apps/ya-agent-platform-web build

.PHONY: docker-build-platform
docker-build-platform: ## Build the combined YA Agent Platform Docker image
	@echo "Building ya-agent-platform Docker image"
	@docker build -t ya-agent-platform:dev .

.PHONY: docker-run-platform
docker-run-platform: ## Run the combined YA Agent Platform Docker image
	@echo "Running ya-agent-platform Docker image"
	@docker run --rm -p 9042:9042 ya-agent-platform:dev

.PHONY: check
check: ## Run code quality tools for all packages
	@echo "Checking lock file consistency with pyproject.toml"
	@uv lock --locked
	@echo "Running pre-commit"
	@uv run pre-commit run -a
	@echo "Running web lint"
	@$(MAKE) web-lint
	@echo "Running web build"
	@$(MAKE) web-build
	@echo "Running pyright"
	@uv run python -m pyright
	@echo "Running deptry for ya-agent-sdk"
	@(cd packages/ya-agent-sdk && uvx deptry ya_agent_sdk)
	@echo "Running deptry for yaacli"
	@(cd packages/yaacli && uvx deptry yaacli)
	@echo "Running deptry for ya-agent-platform"
	@(cd packages/ya-agent-platform && uvx deptry ya_agent_platform)

.PHONY: test
test: ## Run SDK, CLI, and platform tests
	@echo "Running pytest for workspace packages"
	@uv run python -m pytest packages/ya-agent-sdk/tests packages/yaacli/tests packages/ya-agent-platform/tests -n auto -vv --inline-snapshot=disable --cov --cov-config=pyproject.toml --cov-report term-missing

.PHONY: test-sdk
test-sdk: ## Run SDK tests
	@echo "Running SDK pytest"
	@uv run python -m pytest packages/ya-agent-sdk/tests -n auto -vv --inline-snapshot=disable --cov --cov-config=pyproject.toml --cov-report term-missing

.PHONY: test-cli
test-cli: ## Run CLI tests
	@echo "Running CLI pytest"
	@uv run python -m pytest packages/yaacli/tests -n auto -vv --inline-snapshot=disable

.PHONY: test-platform
test-platform: ## Run YA Agent Platform tests
	@echo "Running platform pytest"
	@uv run python -m pytest packages/ya-agent-platform/tests -n auto -vv --inline-snapshot=disable --cov --cov-config=pyproject.toml --cov-report term-missing

.PHONY: test-fix
test-fix: ## Run pytest with inline snapshot updates
	@echo "Running pytest with inline snapshot updates"
	@uv run python -m pytest packages/ya-agent-sdk/tests packages/yaacli/tests packages/ya-agent-platform/tests -vv --inline-snapshot=fix

.PHONY: build
build: clean-build ## Build ya-agent-sdk distribution
	@echo "Building ya-agent-sdk"
	@uv build --package ya-agent-sdk -o dist

.PHONY: build-platform
build-platform: clean-build ## Build ya-agent-platform distribution
	@echo "Building ya-agent-platform"
	@uv build --package ya-agent-platform -o dist

.PHONY: build-all
build-all: clean-build ## Build distributions for all packages
	@echo "Building workspace packages"
	@uv build --all-packages -o dist

.PHONY: clean-build
clean-build: ## Clean build artifacts
	@echo "Removing build artifacts"
	@uv run python -c "from pathlib import Path; import shutil; [shutil.rmtree(path, ignore_errors=True) for path in (Path('dist'), Path('packages/ya-agent-sdk/dist'), Path('packages/yaacli/dist'), Path('packages/ya-agent-platform/dist'))]"

.PHONY: publish
publish: ## Publish built distributions to PyPI
	@echo "Publishing distributions"
	@uv publish dist/*

.PHONY: build-and-publish
build-and-publish: build publish ## Build and publish.

.PHONY: help
help:
	@uv run python -c "import re; [[print(f'\033[36m{m[0]:<20}\033[0m {m[1]}') for m in re.findall(r'^([a-zA-Z_-]+):.*?## (.*)$$', open(makefile).read(), re.M)] for makefile in ('$(MAKEFILE_LIST)').strip().split()]"

.DEFAULT_GOAL := help
