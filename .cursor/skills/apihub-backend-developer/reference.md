# APIHub Backend Developer — Reference

Read this file when you need backend-specific examples or doc-routing detail. Keep `SKILL.md` as the workflow checklist. Generic patterns are in `apihub-go-developer/reference.md`.

## Doc routing (where to update documentation)

| Change type | Update |
|-------------|--------|
| New or changed REST contract | `qubership-apihub-backend/docs/api/APIHUB_API.yaml` (+ Admin/Internal specs if applicable) |
| New feature with design notes | `qubership-apihub-backend/docs/feature_design/<area>/` (see `docs/README.md`) |
| Operational / migration analysis | `qubership-apihub-backend/docs/ops_migration_analysis_guide.md` |
| Local dev setup change | `qubership-apihub-backend/docs/local_development/` |
| AI assistant behavior | `qubership-apihub-backend/docs/feature_design/ai_assistant/` or `docs/static_resources_customization.md` |
| Minor implementation detail | Relevant existing guide only — **not** root `README.md` |

Full index: `qubership-apihub-backend/docs/README.md`.

## Related paths in this monorepo (Helm, E2E)

Prefer updating the matching paths in the same change-set. Use
`apihub-deployment-followup` and `postman-e2e-followup` when the impact is unclear:

| Backend change | Likely follow-up |
|----------------|------------------|
| New env var / secret / feature flag | `helm-templates/qubership-apihub/`, Compose env files, `docs/configuration-reference.md` |
| New cron, probe, port, volume | Helm chart templates |
| New/changed REST API | `qubership-apihub-postman-collections/` + `qubership-apihub-backend/docs/api/*.yaml` |
| New auth or error contract | Postman assertions under `qubership-apihub-postman-collections/` |

## Error codes (`exception/ErrorCodes.go`)

**Good:**

```go
const ExampleNotFound = "999"
const ExampleNotFoundMsg = "Example with id = $id not found"
```

Use existing patterns for parameter placeholders (`$id`, `$param`, etc.). Do not inline error code strings in controllers or services.

## Service.go wiring

- Add `repository.New...` with other repository constructors (end of repository block).
- Add `service.New...` with other services (end of service block).
- Add `controller.New...` with other controllers (end of controller block).
- Use `log.Fatalf` when service construction failure must stop startup (see existing `AiChatService` wiring).

## Migration files

Naming: `{N}_{description}.up.sql` and `{N}_{description}.down.sql` where `N` is the next free integer.

Directory: `qubership-apihub-backend/qubership-apihub-service/resources/migrations/`

Validate (from repository root):

```bash
bash .cursor/skills/apihub-backend-developer/scripts/check_migration_numbers.sh
```

```powershell
powershell -File .cursor/skills/apihub-backend-developer/scripts/check_migration_numbers.ps1
```

## Further reading

- `AGENTS.md` — agent contract (loaded every session)
- `docs/development_guide.md` — API-first, logging, deprecation, PR conventions
