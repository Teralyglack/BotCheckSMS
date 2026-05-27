.PHONY: install run test lint check docker

install:
	pip install -r requirements.txt

run:
	python -m app.main

test:
	pytest

lint:
	ruff check .

check:
	python -m compileall app tests
	pytest
	ruff check .

docker:
	docker compose up --build
