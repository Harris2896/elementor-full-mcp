.PHONY: help mcp-install mcp-test mcp-lint plugin-install plugin-test wp-up wp-down

help:
	@echo "mcp-install   - uv pip install -e mcp-server[dev]"
	@echo "mcp-test      - run python tests"
	@echo "mcp-lint      - ruff check"
	@echo "plugin-install- composer install in wp-plugin"
	@echo "plugin-test   - phpunit in wp-plugin"
	@echo "wp-up         - start wp-env"
	@echo "wp-down       - stop wp-env"

mcp-install:
	cd mcp-server && uv venv && uv pip install -e ".[dev]"

mcp-test:
	cd mcp-server && uv run pytest -v

mcp-lint:
	cd mcp-server && uv run ruff check .

plugin-install:
	cd wp-plugin && composer install

plugin-test:
	cd wp-plugin && composer test

wp-up:
	npx @wordpress/env start

wp-down:
	npx @wordpress/env stop
