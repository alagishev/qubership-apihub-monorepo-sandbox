# Monorepo build guide

This document describes how to build and test the Qubership APIHUB monorepo locally and in CI.

## Prerequisites

Install these toolchains before `go work sync`, `pnpm install`, or `bazel test`.

| Tool | Version | Notes |
|------|---------|--------|
| [Bazelisk](https://github.com/bazelbuild/bazelisk) | 1.x | Reads [`.bazelversion`](../.bazelversion) (Bazel **7.4.1**). Expose it on PATH as `bazel`. |
| Go | **1.26.5** | Matches `go.work` and the `go_sdk` pin in [`MODULE.bazel`](../MODULE.bazel). |
| Node.js | **24.x** | UI and npm packages. |
| pnpm | **9.15.0** | From `packageManager` in [`package.json`](../package.json). Enable with Corepack. |
| Python 3 | 3.10+ | `tools/ci/*.py` needs [PyYAML](https://pypi.org/project/PyYAML/). |
| jq | any recent | Parses JSON from `tools/ci/detect-affected.sh`. |
| Git | 2.x | Clone and path detection. |

`pnpm install` also needs GitHub Packages auth for `@netcracker/*` (see [Quick start](#quick-start)).

On Windows, use **native PowerShell** for Go/Bazel (`--config=go-only`) and
`tools/bazel/run_gazelle.ps1`. Prefer WSL2 for bash CI scripts
(`tools/ci/*.sh`) if you do not have Git Bash. Create `.bazelrc.user` with
`startup --output_user_root=C:/tmp/bazel-out` when `%USERPROFILE%` contains spaces
(the gazelle helper creates this automatically).

Optional: Docker Engine (or Docker Desktop) for local npm OCI builds via
`tools/ci/docker_push_npm.sh`, and for Go images with
`bazel build //qubership-apihub-backend:image`.

### Ubuntu

Run these commands in bash. They work on Ubuntu 22.04/24.04 and inside WSL2 Ubuntu.

1. Install OS packages:

   ```bash
   sudo apt-get update
   sudo apt-get install -y \
     git curl ca-certificates unzip \
     jq python3 python3-pip python3-venv python3-yaml \
     build-essential
   ```

2. Install Go 1.26.5 from the official tarball. Distro `golang-go` is too old:

   ```bash
   GO_VER=1.26.5
   ARCH="$(dpkg --print-architecture)"
   curl -fsSL "https://go.dev/dl/go${GO_VER}.linux-${ARCH}.tar.gz" -o /tmp/go.tgz
   sudo rm -rf /usr/local/go
   sudo tar -C /usr/local -xzf /tmp/go.tgz
   echo 'export PATH=/usr/local/go/bin:$PATH' >> ~/.profile
   export PATH=/usr/local/go/bin:$PATH
   go version
   ```

3. Install Node.js 24.x, then pin pnpm with Corepack:

   ```bash
   curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
   sudo apt-get install -y nodejs
   sudo corepack enable
   corepack prepare pnpm@9.15.0 --activate
   node -v
   pnpm -v
   ```

4. Install Bazelisk and expose it as `bazel`:

   ```bash
   case "$(uname -m)" in
     x86_64) BAZELISK_ARCH=amd64 ;;
     aarch64|arm64) BAZELISK_ARCH=arm64 ;;
     *) echo "unsupported arch: $(uname -m)"; exit 1 ;;
   esac
   curl -fsSL \
     "https://github.com/bazelbuild/bazelisk/releases/latest/download/bazelisk-linux-${BAZELISK_ARCH}" \
     -o /tmp/bazelisk
   sudo install -m 0755 /tmp/bazelisk /usr/local/bin/bazel
   bazel version
   ```

5. Confirm every binary (run `bazel version` from a clone so it can read `.bazelversion`):

   ```bash
   git --version
   go version          # go1.26.5
   node -v             # v24.x
   pnpm -v             # 9.15.0
   python3 -c 'import yaml; print("PyYAML OK")'
   jq --version
   bazel version       # Build label: 7.4.1 after the first run in the repo
   ```

### Windows

**Go + Bazel work natively.** Use PowerShell for gazelle and `bazel build --config=go-only`.
WSL2 Ubuntu is optional for bash-only scripts under `tools/ci/*.sh` (or use Git Bash).

1. Native Windows toolchains. In a new PowerShell:

   ```powershell
   winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
   winget install -e --id GoLang.Go --version 1.26.5 --accept-package-agreements --accept-source-agreements
   winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
   winget install -e --id Bazel.Bazelisk --accept-package-agreements --accept-source-agreements
   winget install -e --id jqlang.jq --accept-package-agreements --accept-source-agreements
   winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
   ```

   Open a **new** terminal so PATH updates apply.

   If winget has no Go **1.26.5**, install the
   [Go 1.26.5 Windows MSI](https://go.dev/dl/go1.26.5.windows-amd64.msi) instead.
   Confirm `node -v` starts with `v24`. If LTS has moved on, install a 24.x build from
   [Node.js downloads](https://nodejs.org/en/download).

3. Pin pnpm and install PyYAML:

   ```powershell
   corepack enable
   corepack prepare pnpm@9.15.0 --activate
   py -3 -m pip install --user pyyaml
   ```

   If `corepack enable` fails on a machine-wide Node.js install, run
   `npm install -g pnpm@9.15.0` instead.

4. If `bazel` is missing after Bazelisk install, copy the Bazelisk executable:

   ```powershell
   $bazelisk = (Get-Command bazelisk).Source
   Copy-Item $bazelisk (Join-Path (Split-Path $bazelisk) 'bazel.exe')
   ```

5. If your Windows user profile path contains a space, create gitignored `.bazelrc.user` at the repo root with:

   ```text
   startup --output_user_root=C:/tmp/bazel-out
   ```

6. Confirm:

   ```powershell
   go version
   node -v
   pnpm -v
   py -3 -c "import yaml; print('PyYAML OK')"
   jq --version
   bazel version
   ```

## Quick start

```bash
# Go workspace (local dev — uses in-tree commons-go)
go work sync

# Install npm dependencies (requires GHCR npm auth for @netcracker/*)
pnpm install

# Refresh Go BUILD files, then build a service binary
# Windows:  powershell -File tools/bazel/run_gazelle.ps1 -Target backend
# Linux:    bash tools/bazel/run_gazelle.sh backend
bazel build --config=go-only \
  //qubership-apihub-backend/qubership-apihub-service:qubership-apihub-service

# Commons-go unit tests
bazel test --config=go-only //qubership-apihub-commons-go/...
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

**Go services** — `rules_oci` (`bazel run //qubership-apihub-backend:push -- --tag dev`).

**npm services (UI, build-task-consumer)** — production `Dockerfile.local` after a pnpm
build (same flow as historical per-repo CI):

```bash
# Auth for private @netcracker packages, then:
bash tools/ci/docker_push_npm.sh ui ghcr.io/<owner>/qubership-apihub-ui local-test
bash tools/ci/docker_push_npm.sh build-task-consumer \
  ghcr.io/<owner>/qubership-apihub-build-task-consumer local-test
```

Go service `BUILD.bazel` deps can be refreshed with:

```bash
powershell -File tools/bazel/run_gazelle.ps1   # Windows
bash tools/bazel/run_gazelle.sh               # Linux / WSL / Git Bash
# fallback if Gazelle misses a dep (e.g. renamed olric module path):
python tools/bazel/sync_go_build_deps.py
```

On a `commons-go` change, detect expands dependents and CI pushes
`backend` / `linter` / `agents-backend` feature tags, then runs PR E2E against those
images (fork GHCR owner is rewritten; `:dev` tags still pull from Netcracker).

## CI

Root workflows under [`.github/workflows/`](../.github/workflows/):

- `ci.yaml` — affected detect, `bazel test`, image push, PR E2E
- `release.yaml` — per-module tags `{module}/v{semver}`
- Hygiene: super-linter, CLA, PR title/commits

Nested `*/.github/workflows/` copies from the pre-monorepo layout are removed; only root workflows run.
