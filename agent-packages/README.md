# Monorepo-local agent packages

Repository-specific APM packages for **qubership-apihub-monorepo-sandbox**.
Generic packages come from
[`qubership-apihub-ci/agent-packages`](https://github.com/Netcracker/qubership-apihub-ci/tree/main/agent-packages)
and [`qubership-ai-packages`](https://github.com/Netcracker/qubership-ai-packages/tree/main/agent-packages).

## Layout

All local packages live under this directory. The **only** APM project is the
repository root (`apm.yml` + `apm.lock.yaml`). Module-level `apm.yml` / harness
trees are not used.

## Packages

| Package | Scope |
|---------|-------|
| `apihub-monorepo` | Always-on monorepo orientation |
| `apihub-deployment-authoring` | Helm, Compose, deployment docs |
| `apihub-deployment-followup` | Backend → deployment follow-up in this repo |
| `backend-conventions` | Backend always-on rules |
| `apihub-backend-developer` | Backend implementation skill |
| `apihub-backend-self-review` | Backend self-review addendum |
| `advanced-verification` | Local backend + Newman verification |
| `postman-e2e-authoring` | Postman/Newman collection authoring |
| `postman-e2e-followup` | Backend → E2E follow-up in this repo |
| `api-diff-authoring` / `api-diff-testing` | api-diff library |
| `api-processor-authoring` / `api-processor-using` | api-processor library |
| `apihub-ui-authoring` | UI TypeScript conventions |

After edits, from the repository root:

```bash
apm install --target cursor,claude --legacy-skill-paths --force
# If a local .worktrees/ tree exists, move it outside the repo first —
# `apm compile` currently discovers stale instructions under worktrees.
apm compile --target cursor,claude --legacy-skill-paths --single-agents --clean
```

Sources under `agent-packages/` and deployed `.cursor/` / `.claude/` harness trees
are **committed**. Gitignore: `apm_modules/`, `agent-packages/**/build/`, `.worktrees/`.
