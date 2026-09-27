# Testing anti-patterns

Adapted from [obra/superpowers](https://github.com/obra/superpowers), MIT, © 2025 Jesse Vincent. See [LICENSE](LICENSE).

Read before writing or changing a test, adding a mock or `monkeypatch`, or adding anything to `src/` that only a test calls.

Tests verify real behaviour. A mock isolates a dependency; it is never the thing under test.

## The rules

1. Never assert on mock behaviour.
2. Never add a test-only function or parameter to `src/`.
3. Never mock a dependency without knowing what side effects the test relies on.

## 1. Asserting on the mock

```python
# Bad: proves only that the stub was called
def test_render_calls_downloads(monkeypatch):
    calls = []
    monkeypatch.setattr(ModuleData, "downloads", lambda self, v: calls.append(v) or [])
    main(["render-site-data"])
    assert calls == ["0.5.7"]
```

Test what the generator writes instead: the JSON on disk, the stderr text, the exit code.

Before any assertion that touches a stub, ask: is this checking the generator, or the stub? If the stub, delete the assertion or remove the stub.

## 2. Test-only code in `src/`

A function, flag or parameter that only a test uses is dead weight in the published package, and the coverage floor then counts it as covered. Test helpers belong in `tests/` or `tests/conftest.py`.

Before adding to `src/`, ask: does anything but a test call this? If not, put it in `tests/`.

## 3. Mocking without understanding

Mocking a function that also writes a file the test later reads makes the test pass or fail for the wrong reason.

Before mocking:

1. What side effects does the real function have?
2. Does the test depend on any of them?
3. If unsure, run the test against the real code first, then mock only the slow or external part.

In this suite the external parts are the network (opt-in, `-m network`) and `npm`, which the suite already fakes. Everything else runs for real: rdflib, pyshacl, the file tree under `tmp_path`, and the installed console script in `tests/test_e2e.py`.

## 4. Incomplete fakes

A fake `.env`, fixture tree or JSON payload with only the keys the test reads hides what downstream code needs. Copy the real fixture (`tests/fixtures/sample-ont`) and change the one thing under test, rather than building a partial one by hand.

## 5. Tests as an afterthought

"Implementation done, tests next" is not done. Tests are part of the implementation. See [SKILL.md](SKILL.md).

## Warning signs

- Setup longer than the test.
- A `monkeypatch` whose removal makes the test fail for a reason unrelated to the behaviour.
- A function in `src/` called only from `tests/`.
- A mock that cannot be justified in one sentence.

When a mock gets complicated, an end-to-end test with real files is usually simpler.
