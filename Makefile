.PHONY: install
install: ## Install the workspace virtual environment and pre-commit hooks
	@echo "Creating workspace environment using uv"
	@uv sync --all-packages
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

.PHONY: check
check: ## Run code quality tools for all packages
	@echo "Checking lock file consistency with pyproject.toml"
	@uv lock --locked
	@echo "Running pre-commit"
	@uv run pre-commit run -a
	@echo "Running pyright"
	@uv run pyright
	@echo "Running deptry for ya-agent-sdk"
	@(cd packages/ya-agent-sdk && uv run --package ya-agent-sdk deptry ya_agent_sdk)
	@echo "Running deptry for yaacli"
	@(cd packages/yaacli && uv run --package yaacli deptry yaacli)

.PHONY: test
test: ## Run SDK and CLI tests
	@echo "Running pytest for workspace packages"
	@uv run python -m pytest packages/ya-agent-sdk/tests packages/yaacli/tests -n auto -vv --inline-snapshot=disable --cov --cov-config=pyproject.toml --cov-report term-missing

.PHONY: test-sdk
test-sdk: ## Run SDK tests
	@echo "Running SDK pytest"
	@uv run python -m pytest packages/ya-agent-sdk/tests -n auto -vv --inline-snapshot=disable --cov --cov-config=pyproject.toml --cov-report term-missing

.PHONY: test-cli
test-cli: ## Run CLI tests
	@echo "Running CLI pytest"
	@uv run python -m pytest packages/yaacli/tests -n auto -vv --inline-snapshot=disable

.PHONY: test-fix
test-fix: ## Run pytest with inline snapshot updates
	@echo "Running pytest with inline snapshot updates"
	@uv run python -m pytest packages/ya-agent-sdk/tests packages/yaacli/tests -vv --inline-snapshot=fix

.PHONY: build
build: clean-build ## Build ya-agent-sdk distribution
	@echo "Building ya-agent-sdk"
	@uv build --package ya-agent-sdk -o dist

.PHONY: build-all
build-all: clean-build ## Build distributions for all packages
	@echo "Building workspace packages"
	@uv build --all-packages -o dist

.PHONY: clean-build
clean-build: ## Clean build artifacts
	@echo "Removing build artifacts"
	@uv run python -c "from pathlib import Path; import shutil; [shutil.rmtree(path, ignore_errors=True) for path in (Path('dist'), Path('packages/ya-agent-sdk/dist'), Path('packages/yaacli/dist'))]"

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
