.PHONY: help install test cov lint type check demo demo-fix format \
	eval-collect eval eval-smoke eval-report

help:
	@echo "make install  安装依赖（uv sync --extra dev）"
	@echo "make test     跑全部测试（离线，无需 key）"
	@echo "make cov      测试 + 覆盖率门禁（>=70%）"
	@echo "make lint     ruff check + format --check"
	@echo "make type     mypy"
	@echo "make check    lint + type + cov（CI 等价）"
	@echo "make demo     离线演示：审查一个 fixture PR（命中 critical，会停在人工审批）"
	@echo "make demo-fix 离线演示：自动修复 dry-run（无 critical，跑完整条链）"
	@echo "make eval-smoke 评测管线冒烟（mock LLM，离线）"
	@echo "make eval-collect 采集 review 金标集（需要 GITHUB_TOKEN）"
	@echo "make eval      真实评测（需要 LLM provider）"
	@echo "make eval-report 渲染评测报告"

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

eval-smoke:
	LLM_PROVIDER=mock uv run python -m eval.run --allow-mock \
		--dataset eval/data/sample_review.jsonl --run-id smoke --out-dir eval/results
	uv run python -m eval.report --run-id smoke --out eval/report-smoke.md

eval-collect:
	uv run python -m eval.collect --repos psf/requests,pallets/flask,encode/httpx \
		--bug 30 --clean 15 --out eval/data/gold_review.jsonl

eval:
	uv run python -m eval.run --dataset eval/data/gold_review.jsonl

eval-report:
	uv run python -m eval.report --out eval/report.md
