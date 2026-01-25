default:
  just --list

lint *args:
    uv run ruff check {{args}}

format:
    uv run ruff format

docs:
    mkdocs serve --livereload
