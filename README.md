# Code Watcher（代码守望者）

[![ci](https://github.com/evinyang-zw/code-watcher/actions/workflows/ci.yml/badge.svg)](https://github.com/evinyang-zw/code-watcher/actions/workflows/ci.yml)

**基于 LangGraph 的有状态代码审查 Agent**：拉取 GitHub PR → 按 hunk 分段审查 → 聚合去重 →
（可选）生成修复补丁并自评估 → 危险操作停在人工审批闸门前。

不是"把 diff 丢给 LLM 再转发评论"的脚本：这里有一条真实的**状态图**（条件边、循环、
reducer、interrupt/resume、checkpoint），以及一套**离线可复现**的工程底座——
无需 token、无需 API key、无需网络即可完整跑通。

```bash
make install
make demo        # 离线跑一个 fixture PR：3 条 finding，命中 critical 后停在人工审批
make demo-fix    # 离线跑自动修复 dry-run：自评估通过 → 展示"将要应用"的补丁
make check       # lint + mypy + 97 个测试 + 覆盖率门禁
```

---

## 工作流

13 个节点、5 组条件边。核心循环与闸门：

```
START → fetch_pr → parse_diff → segment_code → cache_check
                                    ▲                │ (miss)
                                    │                ▼
                         （每段都查缓存）      review_segment ──┐
                                    │                │          │ 循环直到所有 segment 审完
                                    └────────────────┘          │
                                                                ▼
aggregate → suggest_fixes ─┬─(有 critical)──────────────► human_review ──┐
                           ├─(可自动修复)──► self_evaluate ──► auto_fix ──┤
                           └─(其它)──────────────────────────► post_comments ──► END
                                                    auto_fix ─(低置信)─► rollback ─► human_review
```

几个刻意的设计：

| 设计 | 为什么 |
|---|---|
| **typed state + reducer** | `Annotated[list, operator.add]` 让并行/循环写 `segment_reviews` 不会互相覆盖 |
| **每段查缓存** | LRU（O(1)，按 `file:new_content` 哈希）让重复运行不重复花 LLM 钱 |
| **critical → 人工闸门** | 发现 critical 时**不允许**继续自动改代码，先让人看 |
| **自动修复默认 dry-run** | 安全默认：只有显式 `--apply` 才会 push 到 PR 分支 |
| **修复前记录 SHA** | `rollback` 能真正回到修复前状态，而不是"重新读一次 head" |
| **`unidiff` 应用补丁** | 旧实现忽略 `@@` 行号，多 hunk 会改错位置；现在按声明的行号应用并校验上下文 |
| **一次修复尝试** | 图里有循环，但 `fix_attempts` 上限 1，避免无限自我修复（曾经的 `GraphRecursionError`） |

---

## 快速开始

### A. 离线演示（推荐先跑这个；不需要任何 key）

```bash
make install          # uv sync --extra dev
make demo             # 或：uv run python -m src.main --offline https://github.com/acme/demo/pull/101
```

离线模式用 `fixtures/pr-101`（带 critical 的 fixture PR）替代 GitHub、用
`fixtures/pr-101/mock_llm.json` 替代真实 LLM，因此**完全确定性、可断网运行**，
也是所有测试的基础。

```text
=== Code Watcher review ===
(offline mode: fixture PR + mock LLM)
phase: evaluate  findings: 3  critical: 1
  [warning  ] src/calculator.py:3 (correctness) Returning 0 for division by zero ...
  [warning  ] src/calculator.py:8 (performance) File handle is never closed ...
  [critical ] src/config.py:3 (security) Hard-coded database password committed ...
```

命中 critical 的 PR 会停在 `human_review`（`interrupt()`）。加 `--resume` 自动批准并继续：

```bash
uv run python -m src.main --offline --resume https://github.com/acme/demo/pull/101
```

### B. 审查真实 PR

```bash
cp .env.example .env    # 填 GITHUB_TOKEN + LLM key（OpenAI / Anthropic / 任意 OpenAI 兼容端点）
uv run python -m src.main https://github.com/owner/repo/pull/123
```

也可以用 DeepSeek（OpenAI 兼容）：

```bash
LLM_PROVIDER=deepseek LLM_MODEL=deepseek-flash \
LLM_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=sk-... \
uv run python -m src.main <pr-url>
```

---

## 人工闸门与自动修复

| 能力 | 行为 | 怎么用 |
|---|---|---|
| 人工审批 | critical finding 或低置信修复会让图 `interrupt()`，打印 findings/fixes 后暂停 | 默认行为；`--resume` 自动批准 |
| 跨进程恢复 | `--persist .codewatcher/checkpoints.sqlite` 把 checkpoint 落盘（AsyncSqliteSaver） | 第二次进程用 `--resume` 从断点继续 |
| 自动修复 | 先生成 patch，再跑语法/安全/性能自评估，置信度 ≥0.7 才进入"可应用"集合 | `--auto-fix`（默认 dry-run） |
| 真正应用 | 逐文件 commit 到 PR 分支，并记录修复前 SHA | `--auto-fix --apply` |
| 回滚 | 低置信修复会先 `rollback` 回到修复前 SHA，再交给人 | 自动 |

> 自评估的置信度由 `syntax_valid / security / performance / LLM 评估` 加权，
> 并在 `tests/test_graph_e2e.py` 里用 mock LLM 验证了"通过 → 应用"和"不通过 → 回滚"
> 两条路径。它**不是** SWE-bench 式的 benchmark：没有 FAIL_TO_PASS/PASS_TO_PASS
> 语料，只是修复质量的启发式自检。

---

## 离线 fixture 与 Mock LLM

```
fixtures/pr-101/
├── meta.json           # PR 元数据（与 GitHub REST 响应同形）
├── diff.patch          # PR 的 unified diff
├── files_at_head.json  # 每个文件在 head 的内容（auto-fix 用）
└── mock_llm.json       # review / fix / self_evaluate 三类确定性响应
```

`src/github/factory.py` 在 `CODEWATCHER_GITHUB=fake` 时返回 `FakeGitHubClient`；
`src/llm/provider.py` 的 `LLM_PROVIDER=mock` 返回 `MockLLMProvider`（按 prompt 类型
返回 fixture 响应）。二者都只依赖环境变量，节点代码不需要知道自己在离线模式。

---

## 测试与 CI

```bash
make test     # 97 tests, 约 4s，全离线
make cov      # 覆盖率 72%（CI 门禁 70%）
make lint     # ruff check + ruff format --check
make type     # mypy（disallow_untyped_defs）
make check    # 以上全部
```

测试分层：

- **图级 e2e**（`tests/test_graph_e2e.py`）：真正 `workflow.ainvoke()` 跑完整图，
  覆盖"审查所有 segment""critical → interrupt → Command(resume)""auto-fix dry-run"
  "缓存命中""自动修复循环有界"；
- **契约/HTTP**（`tests/test_client.py`）：用 `respx` 在 HTTP 层测 GitHub API；
- **单元**（`tests/test_patch.py` 等）：补丁应用（多 hunk）、diff 解析、缓存、评分；
- **CLI e2e**（`tests/test_main_offline.py`）：子进程跑离线 demo，断言输出与 JSON 摘要。

CI（GitHub Actions）跑 `uv sync --frozen` → ruff → mypy → pytest（覆盖率门禁）→ 离线 demo 冒烟，
全过程**不依赖网络与密钥**。

---

## 评测（自建 review benchmark）

### 协议（为什么这么评）

让 Agent 审查**真实 PR 的 diff**，把它的 finding 与**人类 reviewer 留在同一 PR 上的
行内评论**比对。这不是 SWE-bench（项目不做 issue→patch 修复，没有 FAIL_TO_PASS/
PASS_TO_PASS 语料），而是一个自建协议：真实 PR + 真实人工评论 + 固定口径 + 可复现产物。

- **reviewed 组**：30 个已合并 PR，每个有 1–3 条可信行内评论（过滤 bot、回复、非仓库关联用户）；
- **clean 组**：15 个已合并且被 approve 但没有任何可执行行内评论的 PR，用于测误报；
- 匹配：同文件且行号差 ≤3 视为命中（贪心一对一）；
- 指标：precision / recall / F1 / FPR / 每 PR 评论数，比例给 Wilson 95% CI；
- 产物：`eval/data/gold_review.jsonl`（45 个实例）、`eval/snapshot/`（一次完整运行）与 `eval/report.md`。

### 结果（45 PR = 30 reviewed + 15 clean；DeepSeek-flash，thinking off）

| 指标 | 原始输出 | 发布策略（≥warning、去重、≤5 条/PR） |
|---|---|---|
| Recall（人工评论覆盖率） | **52.4%** [37.7, 66.6] | 23.8% [13.5, 38.5] |
| 其中缺陷类评论（bug/security/perf） | 42.9% (3/7) | 14.3% (1/7) |
| Precision（与人工评论吻合） | **6.9%** [4.6, 10.2] | 13.7% [7.6, 23.4] |
| F1 | 0.121 | 0.174 |
| 干净 PR 误报率 FPR | **93.3%** (14/15) | 73.3% (11/15) |
| 每 PR 评论数 | 10.7 | 2.4 |

### 三个结论（比数字本身重要）

1. **首版是"高召回、低精度"的**：能覆盖一半的人工评论，但每题吐 10 条评论、
   干净 PR 上 93% 会误报——直接发布等于评论轰炸，不可用。
2. **过滤只能换来一半的改善，救不了根因**：加 severity 阈值 + 去重 + 每 PR 上限后，
   precision 翻倍、评论数降到 1/4，但 recall 腰斩、FPR 仍 73%。放宽到 ≤10 条/PR
   时 F1 最高（0.181），牺牲的仍是 recall。
3. **瓶颈在审查环节而不是发布环节**：hunk 级独立审查缺少跨段上下文，导致大量低价值
   评论。下一版要做的是"文件级上下文 + 置信度校准 + 跨段聚合"，而不是继续调过滤器。

### 已知偏差（读数字前必须知道）

- gold 来自人类评论，混有排序/提问类意见（others 30 条），不是纯缺陷标注；类别由关键词启发式推断；
- 行号容差 ±3，同一问题换个行号就算漏；未被人工评论覆盖的 finding 不一定是错的（precision 是下界）；
- 单模型、单次运行、n=45：请用置信区间而不是点估计做比较；有一次实例因超时缺段（报告已标注）；
- **不要把这些数字与任何公开榜单并列**，也不要把 precision/recall 说成"准确率"。

复现命令：`make eval-collect`（需要只读 GITHUB_TOKEN）→ `make eval`（需要 LLM provider）→ `make eval-guard` → `make eval-report`；一次完整运行约 35 分钟（45 PR，DeepSeek-flash）。

## 目录结构

```
src/
├── graph/            # state.py（typed state + defaults）、workflow.py（图）、edges.py（条件边）
│   └── nodes/        # 13 个节点：fetch/parse/segment/cache/review/aggregate/suggest/
│                     #   self_evaluate/auto_fix/rollback/human_review/post_comments/retry
├── github/           # client.py（真实 API）、fake_client.py（fixture）、patch.py（unidiff 应用）、factory.py
├── llm/              # provider.py（OpenAI/Anthropic/mock）、prompts.py、few_shot.py
├── evaluation/       # 语法/安全/性能检查与置信度打分（启发式自评估）
├── cache/            # LRU 缓存（O(1)）
└── schema/           # Pydantic 数据模型
fixtures/             # 两个离线 PR（pr-101 带 critical；pr-102 用于 auto-fix 演示）
tests/                # 97 tests（图级 e2e / HTTP 契约 / 单元 / CLI）
.github/workflows/ci.yml
```

---

## 已知限制（写清楚比藏起来有用）

1. **评测是自建的、规模有限的**：`eval/` 里有一个自建 code-review 评测协议
   （真实 PR + 人工行内评论 + precision/recall/FPR + Wilson CI），口径与已知偏差写在
   `eval/README.md`。它不是 SWE-bench，也不与任何公开榜单可比。
2. **不是 SWE-bench 实现**：本项目只 review diff，不做 repo 探索与 issue→patch 修复，
   没有 FAIL_TO_PASS/PASS_TO_PASS 语料。
3. **修复后重审未实现**：`self_evaluate` 通过后直接发布，不会对 patched 代码再跑一轮 review。
4. **无流式**：没有 SSE/streaming；长任务靠 checkpoint 而非流式进度。
5. **单进程演示向**：没有 GitHub App/webhook 常驻服务，`--persist` 只解决同机跨进程恢复。
6. **LLM 输出解析是宽容的**：非法 JSON/缺字段会被丢弃而不是报错（避免一条 finding 毁掉整次运行）。

---

## License

MIT
