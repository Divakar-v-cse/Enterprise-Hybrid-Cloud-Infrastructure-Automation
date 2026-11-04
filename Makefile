.DEFAULT_GOAL := help
SHELL := /bin/bash

PYTHON ?= python
NODE ?= npm
ENV ?= dev

.PHONY: help install dev api dashboard test test-backend test-frontend lint \
        validate validate-fast tf-fmt tf-validate tf-plan tf-apply \
        ansible-lint ansible-sync ansible-site ansible-validate \
        drift compliance up down clean

help: ## Show the available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	cd backend && $(PYTHON) -m pip install -r requirements-dev.txt
	cd frontend && $(NODE) install

api: ## Run the API with autoreload
	cd backend && uvicorn app.main:app --reload --port 8000

dashboard: ## Run the dashboard dev server
	cd frontend && $(NODE) run dev

dev: ## Reminder for the two-terminal workflow
	@echo "Run 'make api' and 'make dashboard' in separate terminals."

test: test-backend test-frontend ## Run every test suite

test-backend: ## Backend tests with coverage
	cd backend && $(PYTHON) -m pytest -q --cov=app --cov-report=term-missing

test-frontend: ## Frontend typecheck and unit tests
	cd frontend && $(NODE) run typecheck && $(NODE) test

lint: ## Ruff plus TypeScript typecheck
	cd backend && $(PYTHON) -m ruff check app tests
	cd frontend && $(NODE) run typecheck

validate: ## Run every local validation gate
	$(PYTHON) scripts/validate_all.py

validate-fast: ## Validation without the frontend production build
	$(PYTHON) scripts/validate_all.py --fast

tf-fmt: ## Format Terraform
	cd terraform && terraform fmt -recursive

tf-validate: ## Format check and validate both environments
	$(PYTHON) scripts/validate_terraform.py

tf-plan: ## Plan the selected environment (ENV=dev|prod)
	cd terraform/environments/$(ENV) && terraform init -backend-config=backend.hcl && terraform plan -out=tfplan

tf-apply: ## Apply the saved plan (ENV=dev|prod)
	cd terraform/environments/$(ENV) && terraform apply tfplan

ansible-sync: ## Install the required Ansible collections
	cd ansible && ansible-galaxy collection install -r requirements.yml

ansible-lint: ## Lint the Ansible tree
	cd ansible && ansible-lint

ansible-site: ## Converge the selected environment (ENV=dev|prod)
	cd ansible && ansible-playbook playbooks/site.yml -i inventories/$(ENV)/hosts.yml -e target_env=$(ENV)

ansible-validate: ## Prove the configuration baseline (read-only)
	cd ansible && ansible-playbook playbooks/validate.yml -i inventories/$(ENV)/hosts.yml -e target_env=$(ENV)

drift: ## Detect configuration drift (fixture provider)
	$(PYTHON) scripts/drift_detect.py --provider mock

compliance: ## Produce a compliance report (fixture provider)
	$(PYTHON) scripts/compliance_report.py --provider mock --format markdown

up: ## Start the local stack with Docker Compose
	docker compose up --build -d
	@echo "Dashboard: http://localhost:8080  API: http://localhost:8000/docs"

down: ## Stop the local stack
	docker compose down --remove-orphans

clean: ## Remove build and cache artefacts
	rm -rf backend/.pytest_cache backend/.coverage backend/htmlcov backend/.ruff_cache
	rm -rf frontend/dist frontend/coverage frontend/node_modules/.vite
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
