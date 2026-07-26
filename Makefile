
SHELL := /bin/bash

UV ?= uv
DIST_DIR := dist
PACKAGE_NAME := vault-cli
APP_MODULE := app.main

.PHONY: help check clean build install install-editable uninstall reinstall run set-version bump-patch bump-minor bump-major

help: ## Show available commands
	@echo "Usage: make <target>"
	@echo
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "; green="\033[32m"; reset="\033[0m"}; {printf "  " green "%-18s" reset " %s\n", $$1, $$2}'

check: ## Validate required tooling
	@command -v $(UV) >/dev/null 2>&1 || { echo "Error: '$(UV)' is not installed"; exit 1; }

clean: ## Remove build artifacts
	rm -rf build $(DIST_DIR) *.egg-info .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +

build: check ## Build wheel and sdist into ./dist
	$(UV) build --out-dir $(DIST_DIR)

install: build ## Install runtime deps and then install latest built wheel
	$(UV) pip install --break-system-packages --system "hvac>=2.4.0" "pyyaml>=6.0.2" "typer>=0.12.3"
	$(UV) pip install --break-system-packages --system --force-reinstall --no-deps "$$(ls -t $(DIST_DIR)/*.whl | head -n 1)"

install-editable: check ## Install package in editable mode
	$(UV) pip install --break-system-packages --system -e .

uninstall: ## Uninstall package names provided by this project
	-$(UV) pip uninstall --break-system-packages --system -y $(PACKAGE_NAME) vault_cli

reinstall: uninstall install ## Reinstall from fresh build

run: ## Run CLI help from module entrypoint
	$(UV) run python3 -m $(APP_MODULE) --help

set-version: check ## Set explicit version: make set-version VERSION=0.2.0
	@test -n "$(VERSION)" || { echo "Error: VERSION is required, e.g. make set-version VERSION=0.2.0"; exit 1; }
	$(UV) version "$(VERSION)"

bump-patch: check ## Bump patch version (x.y.Z)
	$(UV) version --bump patch

bump-minor: check ## Bump minor version (x.Y.0)
	$(UV) version --bump minor

bump-major: check ## Bump major version (X.0.0)
	$(UV) version --bump major