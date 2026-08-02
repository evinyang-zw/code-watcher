# Code Watcher (代码守望者)

基于 LangGraph 构建的有状态自动化代码审查 Agent。拉取 GitHub PR，对代码进行分段 Review，给出建议甚至自动修复。

## 功能特性

- **LangGraph StateGraph** — 14 个节点的有状态工作流，支持条件路由和中断恢复
- **GitHub PR 集成** — 自动拉取 PR diff，发布行内审查评论
- **分段代码审查** — 按文件/hunk 分段，LLM 独立审查每个片段
- **多维度审查** — 正确性、风格、安全、性能、测试覆盖率
- **自动修复** — 生成 patch，dry-run 模式，逐条提交，冲突检测与回滚
- **SWE-bench 式自评估** — 安全扫描、性能分析、置信度评分、前后质量对比
- **LRU 缓存** — 相同代码段不重复审查
- **Human-in-the-Loop** — 支持人工介入审批修复方案
- **重试机制** — LLM 调用失败自动指数退避重试

## 项目结构

```
code-watcher/
├── src/
│   ├── graph/
│   │   ├── state.py          # LangGraph 状态 Schema (Pydantic)
│   │   ├── workflow.py       # StateGraph 定义 + compile
│   │   ├── edges.py          # 条件路由函数
│   │   └── nodes/            # 12 个节点实现
│   ├── github/
│   │   ├── client.py         # 异步 GitHub API 客户端
│   │   ├── diff_parser.py    # Unified diff 解析器
│   │   └── comment_poster.py # PR 评论发布
│   ├── llm/
│   │   ├── provider.py       # OpenAI/Anthropic 抽象层
│   │   ├── prompts.py        # 审查/修复/自评估 Prompt
│   │   └── few_shot.py       # Few-shot 示例
│   ├── evaluation/
│   │   ├── runner.py         # 语法/lint/测试运行器
│   │   ├── security_scanner.py # 安全漏洞扫描
│   │   ├── performance_analyzer.py # 性能分析
│   │   └── scorer.py         # 置信度评分
│   ├── cache/
│   │   └── review_cache.py   # LRU 缓存 (O(1))
│   └── schema/
│       └── types.py          # Pydantic 数据模型
└── tests/                    # 64 个测试用例
```

## 工作流图

```
START → fetch_pr → parse_diff → segment_code → cache_check
                                                    ↓
                                    ┌── review_segment ◄──┐ (循环)
                                    └──► aggregate ────────┘
                                            ↓
                                      suggest_fixes
                                            ↓
                              ┌─────────────┼─────────────┐
                         auto_fix      human_review    post_comments
                              ↓             ↓              ↓
                         self_evaluate   rollback        END
                              ↓             ↓
                         auto_fix ──► human_review
```

## 安装

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -e ".[dev]"
```

## 配置

创建 `.env` 文件：

```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
# 或
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx

LLM_PROVIDER=openai  # 或 anthropic
LLM_MODEL=gpt-4o     # 或 claude-sonnet-4-20250514
```

## 使用

```bash
# 基本审查
PYTHONPATH=. python -m src.main https://github.com/owner/repo/pull/123

# 启用自动修复 (dry-run)
PYTHONPATH=. python -m src.main https://github.com/owner/repo/pull/123 --auto-fix --dry-run

# 启用自动修复 (实际提交)
PYTHONPATH=. python -m src.main https://github.com/owner/repo/pull/123 --auto-fix

# 详细日志
PYTHONPATH=. python -m src.main https://github.com/owner/repo/pull/123 -v
```

## 测试

```bash
PYTHONPATH=. pytest tests/ -v
```

## 技术栈

- **LangGraph** — 有状态工作流引擎
- **LangChain Core** — LLM 抽象层
- **Pydantic v2** — 数据验证和序列化
- **httpx** — 异步 HTTP 客户端
- **OpenAI / Anthropic** — LLM Provider

## License

MIT
