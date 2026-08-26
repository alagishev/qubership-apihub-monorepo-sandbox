# Monorepo build guide

This document describes how to build and test the Qubership APIHUB monorepo locally and in CI.

## Prerequisites

- [Bazelisk](https://github.com/bazelbuild/bazelisk) (or Bazel 7.4+)
- Go 1.26.5
- pnpm 9.x
- Node.js 24.x (for npm packages and UI)
- On **Windows**, use **WSL2** for Bazel and Go builds

## Quick start

```bash
# Go workspace (local dev — uses in-tree commons-go)
go work sync

# Install npm dependencies (requires GHCR npm auth for @netcracker/*)
pnpm install

# Build and test everything Bazel knows about
bazel test //...
```

## Affected builds (pre-push)

```bash
tools/ci/detect-affected.sh origin/main HEAD
bazel test $(tools/ci/detect-affected.sh origin/main HEAD | jq -r '.bazel_targets[]')
```

## Module layout

See [`tools/modules.yaml`](../tools/modules.yaml) for the dependency graph, release tag prefixes, and E2E profiles.

| Module | Bazel label prefix | Release tag |
|--------|-------------------|-------------|
| commons-go | `//qubership-apihub-commons-go/...` | `commons-go/v*` |
| backend | `//qubership-apihub-backend/...` | `backend/v*` |
| linter | `//qubership-api-linter-service/...` | `linter/v*` |
| agents-backend | `//qubership-apihub-agents-backend/...` | `agents-backend/v*` |
| api-diff | `//qubership-apihub-api-diff/...` | `api-diff/v*` |
| api-processor | `//qubership-apihub-api-processor/...` | `api-processor/v*` |
| build-task-consumer | `//qubership-apihub-build-task-consumer/...` | `build-task-consumer/v*` |
| ui | `//qubership-apihub-ui/...` | `ui/v*` |

## Hybrid dependency model

- **PR / feature branches:** `go.work` and Bazel use **in-tree** `qubership-apihub-commons-go`. npm in-tree packages use
  `workspace:*` via pnpm.
- **Release tags:** Go services pin a published `commons-go` semver in `go.mod`. npm packages are published to GHCR npm
  before downstream modules bump their dependency version.

## Docker / OCI images

Images are built with `rules_oci`:

```bash
bazel build //qubership-apihub-backend:image
bazel run //qubership-apihub-backend:push -- --tag dev
```

Go service `BUILD.bazel` deps can be refreshed with:

```bash
python tools/bazel/sync_go_build_deps.py
```

(Prefer `bazel run //:gazelle-backend` on Linux when Gazelle resolves `go.work` deps correctly.)

On a `commons-go` change, detect expands dependents and CI pushes
`backend` / `linter` / `agents-backend` feature tags, then runs PR E2E against those images.

## CI

Root workflows under [`.github/workflows/`](../.github/workflows/):

- `ci.yaml` — affected detect, `bazel test`, image push, PR E2E
- `release.yaml` — per-module tags `{module}/v{semver}`
- Hygiene: super-linter, CLA, PR title/commits

Nested `*/.github/workflows/` copies from the pre-monorepo layout are removed; only root workflows run.
