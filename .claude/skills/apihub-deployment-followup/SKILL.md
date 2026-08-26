---
name: apihub-deployment-followup
description: Decide whether a backend change requires Helm/Compose/configuration-reference updates in this monorepo and remind with concrete in-repo paths. Use when editing backend config, env defaults, or deployment-facing behaviour — not when already authoring helm-templates/ or docker-compose/.
---

# Deployment follow-up (from backend)

In this monorepo, deployment assets live under the same repository. Your job is to
**remind** when backend work likely needs Helm / Compose / docs updates — and to make
those updates in the same PR when the change is clearly required.

## Paths in this repository

| Field | Value |
|-------|--------|
| **Helm** | `helm-templates/qubership-apihub/` |
| **Compose** | `docker-compose/` |
| **Config map** | `docs/configuration-reference.md` |

## Remind when the backend change includes any of

- New or renamed **environment variables** or **secrets** (including defaults in
  `SystemInfoService` / `config/Config.go` or viper `SetDefault`).
- New **feature flags** or config keys loaded at startup.
- New **ports**, health/readiness probes, or resource limits implied by the service.
- New **background jobs**, cron schedules, or cleanup workers.
- New **volume mounts**, file paths, or object-storage settings.
- New **optional components** toggled at deploy time (extensions, AI chat, linter,
  agents-backend URLs).

## Reminder format

When criteria match, end your message with:

```markdown
### Related paths (deployment follow-up)
- **Helm / Compose / docs**: <concrete checks — values.yaml, Compose env files,
  configuration-reference.md, extension baseUrl, etc.>
```

If the required deployment edits are small and unambiguous, apply them in this monorepo
instead of only reminding. Use the `apihub-deployment-authoring` skill when editing
`helm-templates/`, `docker-compose/`, or deployment docs.

Omit the section when no deployment impact is likely.
