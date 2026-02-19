# Governance

This document defines how Zorora decisions are made, who can approve changes, and how compatibility is protected for users.

Last updated: 2026-02-19

## Scope

Zorora includes:

- Core engine, tool integrations, and research workflows.
- Web and terminal UI.
- Data analysis pipeline.

## Roles

### Project Lead

- Holds final tie-break authority when maintainers cannot reach consensus.
- Approves major governance or strategy changes.

### Maintainers

- Review and merge pull requests.
- Triage issues, label changes, and enforce compatibility policy.
- Manage release readiness.

### Contributors

- Submit issues and pull requests.
- Follow contribution, security, and compatibility requirements.

## Decision Classes

### Routine

Examples:

- Documentation clarity updates.
- New tests.
- Non-breaking bug fixes.
- Tool improvements that do not change existing behavior.

Approval:

- 1 maintainer approval.

### Normative

Examples:

- Changes to workflow behavior or command semantics.
- Changes to API contracts.
- Deprecation notices for commands or behaviors.

Approval:

- 2 maintainer approvals.
- Minimum 7-day public comment window before merge.

### Breaking

Examples:

- Removing commands or tools.
- Changing configuration format.
- Any change requiring user migration.

Approval:

- 2 maintainer approvals plus Project Lead sign-off.
- Explicit migration notes required in release notes.

### Security

Examples:

- Credential handling flaws.
- Vulnerability fixes.
- Supply-chain or dependency risk remediations.

Approval:

- Maintainer + security reviewer (or Project Lead when unavailable).
- May use private disclosure flow until patch is available.

## Compatibility Policy

1. No silent behavior changes to existing commands or workflows.
2. Existing commands and options should remain functional for at least one minor release after deprecation notice.
3. Breaking changes require explicit migration guidance.
4. Additive changes (new tools, optional features, new workflows) are preferred for minor releases.

## Labels and Workflow

Recommended pull request labels:

- `feature`
- `runtime`
- `breaking`
- `security`
- `docs`

Workflow baseline:

1. Open issue or proposal.
2. Classify decision type (`routine`, `normative`, `breaking`, `security`).
3. Merge when approval threshold is met.
4. Document impact in changelog/release notes.

## Release Governance

Release cadence:

- Minor releases on a predictable cadence (for example monthly).
- Patch releases as needed.

Release checklist:

1. Tests pass.
2. Changelog/release notes updated.
3. Migration notes included for normative or breaking changes.
4. Documentation links remain current.

## Conflict Resolution

If maintainers disagree:

1. Attempt consensus in issue/PR discussion.
2. If unresolved, escalate to Project Lead for final decision.

## Governance Changes

Changes to this document are normative and require:

- 2 maintainer approvals, and
- Project Lead sign-off.
