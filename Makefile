.PHONY: lint-flake8

lint-flake8:
	@echo run flake8
	@flake8 src/

.PHONY: lint-isort

lint-isort:
	@echo run isort
	@isort src/

.PHONY: lint-mypy

lint-mypy:
	@echo run mypy
	@mypy src

lint: lint-flake8 lint-isort lint-mypy
