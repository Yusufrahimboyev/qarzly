# CI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run ruff, mypy and pytest unit tests in GitHub Actions on push to `main` and on every pull request.

**Architecture:** A single GitHub Actions job on Python 3.11 that installs `requirements-dev.txt` and runs the three checks in order. First, the two existing mypy errors are fixed, so the pipeline starts green.

**Tech Stack:** GitHub Actions, Python 3.11, ruff, mypy, pytest + pytest-asyncio, aiogram 3.

**Spec:** `docs/superpowers/specs/2026-10-07-ci-pipeline-design.md`

## Global Constraints

- Never touch the production DB: do not set `DATABASE_URL` / `TEST_DATABASE_URL` and do not read `.env`. Run local checks with both variables unset.
- No secrets in the workflow. `permissions: contents: read`.
- Python version: `3.11` (matches Render `PYTHON_VERSION=3.11.9`).
- Dev pins exactly: `pytest~=8.0`, `pytest-asyncio~=0.23`, `ruff~=0.5`, `mypy~=1.10`.
- No push to GitHub, no merge to `main`, without explicit user approval.
- Local verification interpreter: `$V` = scratchpad `venv311` (Python 3.11.15).

## Review Focus

1. **The `exedit` prefix path:** after the mypy fix, the delete/redo actions must keep writing to `_exchanges` / `_ex_replace_index`, not only `_products`. Already covered by `test_debt_creation_handler.py:235,261`. Task 1 must run that file explicitly.
2. **Integration tests in CI:** they must skip, not fail, when there is no DB. Task 2 verifies that the local run with unset env gives `13 skipped`.
3. **Unpinned tool drift:** `ruff~=0.5` / `mypy~=1.10` allow newer minors, so CI can turn red with no code change. Accepted per spec. Note it in the PR description, no extra mechanism (YAGNI).
4. **Pip cache key:** `cache-dependency-path` must point to `requirements-dev.txt`. Otherwise setup-python looks for `requirements.txt` only and the cache misses dev tools. Covered by actionlint plus a review in Task 2.
5. **Fork PRs:** the workflow has no secrets and only read permission, so fork PRs are safe. Verified by reading the YAML in Task 2.

---

### Task 1: Fix the two mypy `update_data` errors

**Files:**
- Modify: `bot/presentation/handlers/debt_creation.py` (the `update_data(**{...})` calls in `cb_edit_delete` and `cb_edit_redo`, mypy-reported lines 1119 and 1147)
- Test: `tests/test_debt_creation_handler.py` (existing tests, unchanged)

**Interfaces:** none. Internal call change only. `FSMContext.update_data(data: Mapping[str, Any] | None = None, **kwargs)`.

- [ ] **Step 1: Confirm the failing check**

Run: `$V/bin/mypy bot`
Expected: `Found 2 errors in 1 file`, both `[arg-type]` at `debt_creation.py:1119` and `:1147`.

- [ ] **Step 2: Replace both `**{key: value}` calls with a positional dict**

`state.update_data({list_key: items})` and `state.update_data({_EDIT_TARGETS[prefix][1]: index})`. Touch nothing else.

- [ ] **Step 3: Verify mypy passes and handler behavior is unchanged**

Run: `$V/bin/mypy bot` → `Success: no issues found in 94 source files`
Run: `$V/bin/python -m pytest tests/test_debt_creation_handler.py -q` → all pass, 0 failed
Run: `$V/bin/ruff check .` → `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add bot/presentation/handlers/debt_creation.py
git commit -m "fix(bot): pass update_data dict positionally to satisfy mypy"
```

### Task 2: CI workflow + dev requirements

**Files:**
- Create: `requirements-dev.txt`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: Task 1 (mypy clean).
- Produces: workflow named `CI`, job `checks`. The steps run exactly `ruff check .`, `mypy bot`, `pytest -q`.

- [ ] **Step 1: Write `requirements-dev.txt`**

Contents exactly: `-r requirements.txt`, then the four dev pins from Global Constraints, one per line.

- [ ] **Step 2: Prove the file installs into a clean 3.11 env and the checks pass (the "test")**

Create a fresh venv in the scratchpad (`uv venv -p python3.11 <scratchpad>/venv-ci`), then `uv pip install -r requirements-dev.txt` into it. With `DATABASE_URL` and `TEST_DATABASE_URL` unset, run the three commands in workflow order.
Expected: ruff `All checks passed!`, mypy `Success`, pytest `241 passed, 13 skipped`.

- [ ] **Step 3: Write `.github/workflows/ci.yml`**

- `name: CI`
- `on: push: branches: [main]` and `pull_request:`
- top-level `permissions: contents: read`
- job `checks`, `runs-on: ubuntu-latest`
- steps: `actions/checkout@v4`; `actions/setup-python@v5` with `python-version: "3.11"`, `cache: pip`, `cache-dependency-path: requirements-dev.txt`; `pip install -r requirements-dev.txt`; then one named step each for `ruff check .`, `mypy bot`, `pytest -q`.
- No `env:` block, no secrets.

- [ ] **Step 4: Lint the workflow**

Run: `uvx --from actionlint-py actionlint .github/workflows/ci.yml`
Expected: no output, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add requirements-dev.txt .github/workflows/ci.yml
git commit -m "ci: run ruff, mypy and unit tests on push and PR"
```

### Task 3 (only with user approval): Real run on GitHub

- [ ] **Step 1:** Ask the user. Push branch `worktree-ci-pipeline` and open a **draft** PR against `main`.
- [ ] **Step 2:** `gh run watch` → the `CI` run concludes `success`.
- [ ] **Step 3:** Report the run URL. Do not merge.
