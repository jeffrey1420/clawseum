SHELL := /usr/bin/env bash

DOCKER_COMPOSE ?= docker compose
NPM ?= npm
PYTHON ?= python3

SEED_COUNT ?= 6
SEED_RANDOM ?= 42
SEED_OUTPUT ?= tmp/seed-round.json

.PHONY: dev build deploy seed logs

dev:
	@echo "[dev] Starting local dependencies (postgres, redis)..."
	@$(DOCKER_COMPOSE) up -d postgres redis
	@echo "[dev] Starting frontend dev server..."
	@cd frontend && $(NPM) install && $(NPM) run dev

build:
	@echo "[build] Building frontend..."
	@cd frontend && $(NPM) install && $(NPM) run build
	@echo "[build] Validating backend Python modules..."
	@$(PYTHON) -m compileall backend

deploy:
	@echo "[deploy] Building and starting CLAWSEUM stack..."
	@$(DOCKER_COMPOSE) up -d --build
	@echo "[deploy] Stack started. Run 'make logs' to inspect services."

seed:
	@echo "[seed] Generating sample mission output..."
	@mkdir -p $(dir $(SEED_OUTPUT))
	@$(PYTHON) backend/arena-engine/simulation.py \
		--seed $(SEED_RANDOM) \
		--count $(SEED_COUNT) \
		--json-out $(SEED_OUTPUT)
	@echo "[seed] Wrote $(SEED_OUTPUT)"

logs:
	@$(DOCKER_COMPOSE) logs -f --tail=200