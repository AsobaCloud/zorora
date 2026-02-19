# Contributing to Zorora

Thanks for contributing to Zorora.

This guide covers setup, validation, and pull request expectations.

## Development Setup

```bash
git clone https://github.com/AsobaCloud/zorora.git
cd zorora
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For the full dependency set (web UI, data analysis):

```bash
pip install -e .[full]
```

## Validate Changes Locally

Run tests:

```bash
pytest -q
```

## Change Types

Use these labels in pull requests:

- `feature`
- `runtime`
- `breaking`
- `security`
- `docs`

Decision and approval rules are defined in `GOVERNANCE.md`.

## Pull Request Requirements

1. Explain what changed and why.
2. State whether the change is `routine`, `normative`, `breaking`, or `security`.
3. Include tests for behavior changes.
4. Update documentation for user-facing behavior changes.
5. Include migration notes for breaking changes.

## Commit Guidance

- Keep commits focused and atomic.
- Use clear commit messages in imperative mood.
- Do not include secrets or credentials.

## Reporting Issues

- Use issue templates in `.github/ISSUE_TEMPLATE`.
- For vulnerabilities, use `SECURITY.md` instead of public issues.
