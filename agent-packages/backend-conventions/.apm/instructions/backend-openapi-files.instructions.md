---
description: Backend OpenAPI file list and sync requirements
applyTo: "qubership-apihub-backend/docs/api/**,qubership-apihub-backend/qubership-apihub-service/controller/**"
---

# Backend OpenAPI Files

Any REST endpoint or contract change **must** update the relevant OpenAPI files under
`qubership-apihub-backend/docs/api/`:

- Public API: `qubership-apihub-backend/docs/api/APIHUB_API.yaml`
- Admin API: `qubership-apihub-backend/docs/api/Admin API.yaml`
- Internal API: `qubership-apihub-backend/docs/api/APIHUB_API_internal.yaml` (when internal endpoints change)

Do not introduce breaking public API changes without versioning and deprecation per
`qubership-apihub-backend/docs/development_guide.md`.
