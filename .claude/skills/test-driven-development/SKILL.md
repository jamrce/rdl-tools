---
name: test-driven-development
description: Use when implementing any feature, bug fix or behaviour change in rdl-tools, before writing implementation code. Red, green, refactor with pytest.
---

# Test-driven development

Adapted from the `test-driven-development` skill in [obra/superpowers](https://github.com/obra/superpowers), MIT, © 2025 Jesse Vincent. See [LICENSE](LICENSE).

Write the test first. Watch it fail. Write the least code that makes it pass.

A test never seen failing is not known to test anything.

## Scope

Always: new behaviour, bug fixes, behaviour changes, refactors of untested code.

Ask the maintainer before skipping it for: throwaway exploration, generated files, configuration (`pyproject.toml`, workflows, `.devcontainer/`), prose docs.

## The rule

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Code written before its test is deleted and written again from the test. It is not kept as a reference, and not adapted while the test is written.

## Cycle

### 1. Red — write one failing test

One behaviour per test. The name states the behaviour. Real code, real files under `tmp_path`, real `main([...])` calls; no mocks unless the dependency is a network or a subprocess the suite already fakes.

Good:

```python
def test_a_missing_artifact_tree_warns_on_stderr(module_copy: Path, capsys):
    assert main(["render-site-data", "--module-dir", str(module_copy)]) == 0
    assert "no artifact tree at website/static/v0.5.7/ont/" in capsys.readouterr().err
```

Bad:

```python
def test_downloads(monkeypatch):
    monkeypatch.setattr(render_site_data, "downloads", lambda self, v: [])
    ...
```

Vague name, and it tests the stub, not the generator.

Where the test goes follows the existing layout: unit tests beside their subject (`tests/test_render_site_data.py`, `tests/test_init.py`, …); anything asserted over a full installed run goes in `tests/test_e2e.py`.

### 2. Verify red — mandatory

```sh
.venv/bin/python -m pytest tests/test_x.py::test_name
```

Confirm:

- The test **fails**; it does not error (no `ImportError`, `NameError`, fixture error).
- The failure message is the expected one.
- It fails because the behaviour is missing, not because of a typo.

Passes at once: it tests existing behaviour. Fix the test. Errors: fix the error and run again until it fails for the right reason.

Record the one decisive line of the failure. Whoever reviews the change reads it.

### 3. Green — least code

The simplest code that passes this test. No extra options, no refactoring of neighbouring code, nothing the test does not ask for.

### 4. Verify green — mandatory

Run the test, then the whole suite:

```sh
.venv/bin/python -m pytest tests/test_x.py::test_name
.venv/bin/python -m pytest
```

Confirm the test passes, every other test passes, and the output has no new warnings. `filterwarnings` turns a `DeprecationWarning` from `rdl_tools` into an error.

Test fails: fix the code, not the test. Another test fails: fix it now.

### 5. Refactor

Only once green. Remove duplication, improve names, extract helpers. Add no behaviour. Stay green.

### 6. Repeat

Next behaviour, next failing test.

## Good tests

- **Minimal**: one thing. An "and" in the name means two tests.
- **Clear**: the name describes behaviour, like the existing `test_downloads_are_empty_until_the_pin_is_actually_generated`.
- **Intent**: shows the API as a caller uses it — through `main([...])` or the public function, not private state.

## Rationalisations that mean stop

| Thought | Reality |
|---|---|
| "Too simple to test" | Simple code breaks. The test takes a minute. |
| "Test after" | A test that passes immediately proves nothing. |
| "Already checked it by hand" | No record, cannot be re-run. |
| "Deleting this work is wasteful" | Sunk cost. Untested code is the waste. |
| "Explore first" | Fine. Throw the exploration away, then start with a test. |
| "Hard to test" | Hard to test means hard to use. Simplify the interface. |
| "Existing code has no tests" | Add them for the part being changed. |

Any of these, or code before a test, or a test that passed first time: delete the code and start again.

## Checklist before claiming done

- [ ] Every new function or behaviour has a test.
- [ ] Each test was seen failing, for the expected reason, and that line is recorded.
- [ ] The code is the least that passes.
- [ ] The whole suite passes with no new warnings.
- [ ] Mocks only where unavoidable — see [testing-anti-patterns.md](testing-anti-patterns.md).
- [ ] Edge cases and error paths (exit codes `1` and `2`) are covered.

A box that cannot be ticked means TDD was skipped. Start again.

## When stuck

| Problem | Action |
|---|---|
| Unsure how to test | Write the wished-for call and its assertion first. Ask the maintainer. |
| Test too complicated | The design is too complicated. Simplify it. |
| Everything needs mocking | The code is too coupled. Pass the dependency in. |
| Setup is huge | Extract a fixture. Still huge: simplify the design. |

A bug found later gets a failing test that reproduces it before any fix.
