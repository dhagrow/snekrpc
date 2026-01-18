default:
  just --list

lint:
    uv run ruff check

format:
    uv run ruff format

docs:
    mkdocs serve --livereload
