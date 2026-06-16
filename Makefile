.PHONY: dev test lint

dev:
	docker compose up --build

test:
	pytest

lint:
	python -m compileall app tests
