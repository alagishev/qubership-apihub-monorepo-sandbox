---
name: postman-e2e-followup
description: Decide whether a backend REST/OpenAPI change requires Newman E2E updates under qubership-apihub-postman-collections/ in this monorepo. Use after contract changes — not when already authoring collections.
---

# Postman E2E follow-up (from backend)

In this monorepo, E2E collections live under `qubership-apihub-postman-collections/`.
Remind when backend work likely needs collection updates — and make those updates in
the same PR when the change is clearly required.

## Paths in this repository

| Field | Value |
|-------|--------|
| **Collections** | `qubership-apihub-postman-collections/` |
| **Backend OpenAPI** | `qubership-apihub-backend/docs/api/` |
| **Backend notes** | `qubership-apihub-backend/docs/postman_collections.md`, `docs/postman/` |

## Remind when the backend change includes any of

- New or changed **REST endpoints** (method, path, query, headers).
- Changed **request or response** JSON shape or status codes.
- New **auth** or permission behaviour worth asserting in integration tests.
- New **error codes** or validation rules that E2E suites should cover.

## Reminder format

When criteria match, end your message with:

```markdown
### Related paths (E2E follow-up)
- **Postman / Newman** (`qubership-apihub-postman-collections/`): <concrete requests/tests
  to add or update; align with OpenAPI under qubership-apihub-backend/docs/api/>
```

If the required collection edits are small and unambiguous, apply them in this monorepo
instead of only reminding. Use the `postman-e2e-authoring` skill when editing collections.

Omit the section when no E2E impact is likely (internal refactors, non-REST changes).
