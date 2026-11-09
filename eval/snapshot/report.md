# Code Watcher · Review benchmark



- run_id: `real-2026-11-09`
- runs with a segment/LLM error: 1/45 (their unfetched segments lower recall; see per-instance table)
- dataset: `eval/data/gold_review.jsonl`
- provider: `deepseek` / model: `deepseek-flash`
- instances: 45 (30 reviewed PRs + 15 clean PRs)

## Headline

| Metric | Value | 95% CI (Wilson) | n |
|---|---|---|---|
| Recall (human comments found) | 52.4% | [37.7, 66.6] | 22/42 |
| Precision (findings matching a comment) | 6.9% | [4.6, 10.2] | 22/320 |
| Recall on defect-like comments (bug/security/performance) | 42.9% | [15.8, 75.0] | 3/7 |
| Recall on comments with a concrete code suggestion | 54.5% | [28.0, 78.7] | 6/11 |
| F1 | 0.121 | — | — |
| False-positive rate (clean PRs) | 93.3% | [70.2, 98.8] | 14/15 |
| Findings per bug-fix PR | 10.67 | — | 320 findings |

> Precision is measured against human review comments only: an unmatched finding is not necessarily wrong, just not corroborated by the reviewer.

## Recall by human-comment category

| Category | Recall | Matched / total |
|---|---|---|
| bug | 42.9% | 3/7 |
| other | 56.7% | 17/30 |
| style | 40.0% | 2/5 |

## Noise reduction (raw model output vs publishing guard)

Guard: drop below `warning`, dedupe, cap 5 comments/PR.

| Metric | Raw | Guarded |
|---|---|---|
| Findings per bug-fix PR | 10.67 | 2.43 |
| Precision | 6.9% | 13.7% |
| Recall | 52.4% | 23.8% |
| False-positive rate (clean PRs) | 93.3% | 73.3% |

## Failure taxonomy (missed human comments)

| Category | Missed |
|---|---|
| other | 13 |
| bug | 4 |
| style | 3 |

## Per-instance results

| Instance | Kind | Gold | Findings | Matched gold | Error |
|---|---|---|---|---|---|
| python-poetry_poetry-11204 | clean | 0 | 16 | 0 |  |
| python-poetry_poetry-11129 | clean | 0 | 0 | 0 |  |
| python-poetry_poetry-11099 | clean | 0 | 19 | 0 |  |
| python-poetry_poetry-11141 | bug | 2 | 13 | 1 |  |
| python-poetry_poetry-11131 | bug | 1 | 9 | 0 |  |
| python-poetry_poetry-11171 | clean | 0 | 7 | 0 |  |
| python-poetry_poetry-11175 | clean | 0 | 2 | 0 |  |
| python-poetry_poetry-11093 | clean | 0 | 3 | 0 |  |
| python-poetry_poetry-11107 | clean | 0 | 4 | 0 |  |
| python-poetry_poetry-11152 | clean | 0 | 2 | 0 |  |
| python-poetry_poetry-11169 | clean | 0 | 4 | 0 |  |
| python-poetry_poetry-11046 | clean | 0 | 4 | 0 |  |
| python-poetry_poetry-11014 | clean | 0 | 2 | 0 |  |
| python-poetry_poetry-11025 | clean | 0 | 9 | 0 |  |
| python-poetry_poetry-10975 | bug | 1 | 8 | 1 |  |
| python-poetry_poetry-11022 | clean | 0 | 20 | 0 |  |
| python-poetry_poetry-11003 | clean | 0 | 15 | 0 |  |
| python-poetry_poetry-11133 | bug | 1 | 3 | 1 |  |
| python-poetry_poetry-11055 | clean | 0 | 1 | 0 |  |
| python-poetry_poetry-11042 | bug | 3 | 40 | 3 |  |
| python-poetry_poetry-11037 | bug | 1 | 6 | 0 |  |
| python-poetry_poetry-10907 | bug | 1 | 6 | 1 |  |
| python-poetry_poetry-10787 | bug | 1 | 23 | 0 |  |
| python-poetry_poetry-10721 | bug | 2 | 14 | 1 |  |
| python-poetry_poetry-10720 | bug | 2 | 5 | 1 |  |
| python-poetry_poetry-10699 | bug | 1 | 9 | 0 |  |
| python-poetry_poetry-10648 | bug | 3 | 5 | 1 |  |
| python-poetry_poetry-10653 | bug | 1 | 34 | 1 |  |
| python-poetry_poetry-10361 | bug | 2 | 17 | 2 |  |
| python-poetry_poetry-10110 | bug | 1 | 5 | 1 |  |
| python-poetry_poetry-10077 | bug | 1 | 4 | 0 |  |
| python-poetry_poetry-10275 | bug | 2 | 12 | 1 |  |
| python-poetry_poetry-10276 | bug | 1 | 7 | 1 |  |
| python-poetry_poetry-10187 | bug | 2 | 11 | 1 |  |
| python-poetry_poetry-9327 | bug | 1 | 21 | 1 |  |
| python-poetry_poetry-10587 | bug | 1 | 18 | 1 |  |
| encode_httpx-3445 | bug | 1 | 0 | 0 |  |
| encode_httpx-3440 | bug | 1 | 2 | 0 |  |
| encode_httpx-3418 | bug | 1 | 2 | 1 |  |
| encode_httpx-3387 | bug | 2 | 29 | 0 |  |
| encode_httpx-3109 | bug | 1 | 5 | 0 |  |
| encode_httpx-3245 | bug | 1 | 0 | 0 | TimeoutError:  |
| encode_httpx-3064 | bug | 2 | 5 | 1 |  |
| encode_httpx-3095 | bug | 1 | 2 | 1 |  |
| encode_httpx-3045 | bug | 1 | 5 | 0 |  |

## Sample misses (human comments the agent did not cover)

- `python-poetry_poetry-11141` tests/console/commands/test_remove.py:56 (other) — Can you move the new tests to the end? (I like having basic tests first and more involved tests later.)
- `python-poetry_poetry-11131` src/poetry/installation/chooser.py:237 (other) — With this change it is not deterministic anymore which hash is checked. We probably still want to check the hash with th
- `python-poetry_poetry-11037` src/poetry/utils/helpers.py:361 (bug) — Wouldn't it make more sense to also always set `new_attrs["uname"]` and `new_attrs["gname"]` to `""` because now we hand
- `python-poetry_poetry-10787` src/poetry/console/commands/init.py:169 (other) — I think this still makes sense because `[]` just means that there is no default. E.g., it is also `Description []:`
- `python-poetry_poetry-10721` src/poetry/console/commands/update.py:81 (bug) — I do not think extracting the package name and ignoring the rest makes sense. The interface of `update` is to pass packa
- `python-poetry_poetry-10720` src/poetry/packages/locker.py:619 (bug) — sorting is probably better achieved at line 524
```
          for dependency in sorted(
              package.requires,

- `python-poetry_poetry-10699` src/poetry/puzzle/provider.py:498 (other) — The original check ended up comparing data like this:
```
{'file': 'pkg.whl', 'hash': 'sha256:abc...'}
{'file': 'pkg.
- `python-poetry_poetry-10648` tests/utils/env/test_env_manager.py:1315 (other) — `mocker` seems to be unused.
- `python-poetry_poetry-10648` tests/utils/env/test_env_manager.py:1320 (other) — We do not need `mocked_python_register,` do we?
- `python-poetry_poetry-10077` pyproject.toml:7 (other) — ```suggestion
    "poetry-core @ git+https://github.com/python-poetry/poetry-core.git@main",
```

python-poetry/poet

## Sample unmatched findings (not corroborated)

- `python-poetry_poetry-11204` src/poetry/utils/env/python/manager.py:175 [warning] Removing the `cast("str", ...)` from `name` drops the explicit type assertion. If `self._python.name` is typed as `str |
- `python-poetry_poetry-11204` src/poetry/utils/env/python/manager.py:179 [warning] Removing `cast("Path", ...)` from `executable` weakens the type contract. If `self._python.interpreter` is not staticall
- `python-poetry_poetry-11099` src/poetry/installation/wheel_installer.py:7 [suggestion] New imports `threading` and `WeakValueDictionary` are added but not used in the shown segment. If they are used elsewher
- `python-poetry_poetry-11099` src/poetry/installation/wheel_installer.py:44 [critical] WeakValueDictionary is unsafe for per-path locks: if no thread currently holds a strong reference to a lock (e.g., betwe
- `python-poetry_poetry-11141` src/poetry/console/commands/remove.py:219 [suggestion] `removed_groups` is initialized but not used within this segment. If it's intended to track groups removed across the su
- `python-poetry_poetry-11141` src/poetry/console/commands/remove.py:241 [warning] The condition now references `to_remove`, but the surrounding context (the loop that populates `to_remove`) is not shown
- `python-poetry_poetry-11131` src/poetry/installation/chooser.py:224 [warning] The set comprehension over `package.files` is now recomputed for every link in `ordered_links`, making this O(links × fi
- `python-poetry_poetry-11131` src/poetry/installation/chooser.py:224 [warning] Behavior change: previously if `package.files` was non-empty but no hash matched the link, the code still had a non-empt
- `python-poetry_poetry-11171` src/poetry/console/commands/publish.py:95 [warning] Only double quotes are escaped before interpolating dist_dir into a shell-like argument string parsed by cleo's tokenize
- `python-poetry_poetry-11171` src/poetry/console/commands/publish.py:95 [suggestion] The escaping logic is duplicated inline and is fragile; consider using a shared helper (e.g. shlex.quote or a dedicated 

## Limitations

- Gold = human inline review comments; praise/approval comments are filtered out heuristically, so both the gold set and the categories carry labeling noise.
- Matching uses file + line tolerance (±3); a correct finding on a different line counts as a miss.
- Unmatched findings may still be valid issues the reviewer did not comment on (precision is a lower bound).
- Single reviewer, single run, one model: use the CIs, not the point estimates, for comparisons.
- This is a self-built review benchmark; it is **not** SWE-bench and its numbers are not comparable to leaderboards.
