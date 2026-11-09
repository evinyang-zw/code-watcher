# Review benchmark（自建 code-review 评测）

这个目录实现了一个**自建**的代码审查评测协议：让 Code Watcher 审查一批真实 PR，
把它的 finding 与**人类 reviewer 留下的行内评论**对比，报告 precision / recall /
F1 / false-positive rate，并给出失败分类。

> 这不是 SWE-bench，也不与任何公开榜单可比。项目只 review diff，不做
> issue→patch 修复，没有 FAIL_TO_PASS/PASS_TO_PASS 语料。这里用的是"真实 PR +
> 真实人工评论 + 固定口径 + 可复现产物"的自建协议。

## 数据从哪来

`eval/collect.py` 通过 GitHub REST API 采集**已合并**的 PR：

- **bug-fix 组**：标题以 `fix/bug/hotfix` 开头，或带 `bug/fix` 标签；要求有 1–3 条
  行内 review 评论（过滤掉 LGTM/thanks 之类的非问题性评论、过滤 bot）；
- **干净组**：标题以 `docs/chore/refactor/test/ci/build` 开头，或带
  `docs/chore/refactor` 标签；要求**没有**可执行的行内评论；
- 两组都要求：改动文件 ≤10 个、增删行数 3–250、diff 里至少有一个 `.py` 文件。

采集后的实例存成 JSONL（`eval/data/gold_review.jsonl`），字段见 `eval/schema.py`。

## 怎么评

1. 每个实例通过离线 fixture 喂给同一个工作流（`CODEWATCHER_GITHUB=fake`），
   LLM 用真实 provider（`eval/run.py` 拒绝 `LLM_PROVIDER=mock`）；
2. 匹配规则：finding 与人类评论**同文件**且行号差 ≤3 视为命中（贪心一对一匹配）；
3. 指标：
   - `recall = 命中的 gold / gold 总数`（bug-fix 组）
   - `precision = 命中评论的 finding / finding 总数`（bug-fix 组）
   - `F1`
   - `FPR = 有 finding 的干净 PR 数 / 干净 PR 数`
   - 每类人类评论（bug/security/performance/style/other）的 recall 与漏检分布
4. 比例指标一律给 **Wilson 95% 置信区间**，避免小样本点估计被过度解读。

## 命令

```bash
# 1) 采集（需要只读 GitHub token；公开数据，不需要写权限）
GITHUB_TOKEN=ghp_xxx python -m eval.collect \
  --repos psf/requests,pallets/flask,encode/httpx --bug 30 --clean 15

# 2) 运行评测（需要真实 LLM；示例用 DeepSeek 的 OpenAI 兼容端点）
LLM_PROVIDER=deepseek LLM_MODEL=deepseek-flash \
LLM_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=sk-... \
python -m eval.run --dataset eval/data/gold_review.jsonl

# 3) 生成报告
python -m eval.report --out eval/report.md
```

`eval/results/` 保存每次运行的逐实例 JSON 与 summary；`eval/report.md` 是渲染后的报告。

## 已知偏差（比数字更重要）

- gold 来自人类评论，类别由关键词启发式推断，带噪声；
- 行号容差 ±3，同一问题换个行号就算漏；
- 未被人类评论覆盖的 finding 不一定是错的（precision 是下界）；
- 单 reviewer、单次运行、单模型：比较时应看置信区间，而不是点估计；
- 因此**不要把这里的数字与其它项目的数字并列**，也不要把"precision/recall"
  改写成"准确率"。
