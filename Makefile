.PHONY: help install test cov lint type check demo demo-fix format

help:
	@echo "make install  安装依赖（uv sync --extra dev）"
	@echo "make test     跑全部测试（离线，无需 key）"
	@echo "make cov      测试 + 覆盖率门禁（>=70%）"
	@echo "make lint     ruff check + format --check"
	@echo "make type     mypy"
	@echo "make check    lint + type + cov（CI 等价）"
	@echo "make demo     离线演示：审查一个 fixture PR（命中 critical，会停在人工审批）"
	@echo "make demo-fix 离线演示：自动修复 dry-run（无 critical，跑完整条链）"

install:
	uv sync --extra dev

test:
	uv run pytest tests/ -q

cov:
	uv run pytest tests/ -q --cov=src --cov-report=term-missing --cov-fail-under=70

lint:
	uv run ruff check .
	uv run ruff format --check .

type:
	uv run mypy

format:
	uv run ruff format .

check: lint type cov

demo:
	uv run python -m src.main --offline https://github.com/acme/demo/pull/101

demo-fix:
	uv run python -m src.main --offline --fixture-dir fixtures/pr-102 --auto-fix \
		https://github.com/acme/demo/pull/102
