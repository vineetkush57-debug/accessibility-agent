.PHONY: setup run demo test test-all eval lint

setup:
	python scripts/dev.py setup

run:
	python scripts/dev.py run

demo:
	python scripts/dev.py demo

test:
	python scripts/dev.py test

test-all:
	python scripts/dev.py test-all

eval:
	python scripts/dev.py eval

lint:
	python scripts/dev.py lint
