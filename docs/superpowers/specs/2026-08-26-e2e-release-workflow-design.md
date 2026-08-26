# End-to-end release workflow design

## Goal

Add a manual GitHub Actions workflow that orchestrates an end-to-end release for the APIHUB monorepo.
The workflow must:

- determine which modules need a release;
- compute new semantic versions automatically;
- create all required module tags;
- publish module releases only where changes exist, unless the operator selects `release all`;
- write release notes into each module release;
- create a global application tag in `X.Y.Z` format; and
- publish global release notes for the application as a whole.

## Inputs

The release workflow uses `workflow_dispatch` and accepts these inputs:

- `sprint_name` — required; the Project/Sprint name used for global release notes;
- `release_mode` — required; one of `changed` or `all`.

## Existing assets to reuse

The design reuses these repository assets:

- `tools/modules.yaml` as the source of module metadata, tag prefixes, OCI targets, and dependent modules;
- `.github/workflows/release.yaml` as the tag-driven module publish workflow;
- `tools/ci/detect-affected.sh` patterns for identifying touched modules from git changes;
- the earlier component release-notes logic from `be-repo-rns-generator.py`;
- the earlier global release-notes logic from `app-apihub-rns-generator.py`.

## High-level flow

1. A user starts the new release workflow manually.
2. The workflow computes a release plan for all modules in `tools/modules.yaml`.
3. The workflow creates new tags for each module in the plan.
4. The existing module release workflow publishes each tagged module.
5. After module releases are created, the workflow computes the global application version.
6. The workflow creates the global `X.Y.Z` tag and publishes the global release.

## Module release plan

For each module from `tools/modules.yaml`, the workflow finds the latest tag that matches the module tag prefix, for
example `backend/v*` or `ui/v*`.

The workflow then checks whether the module path has changed since the previous module tag. If a
module has never been tagged, it compares against the previous global `X.Y.Z` tag when one exists.

- if `release_mode=changed`, the module is selected when its own path changed;
- if `release_mode=all`, the module is always selected.

After the initial selection, the workflow expands the plan with transitive dependants from `tools/modules.yaml`. This
means that an upstream change in `commons-go`, `api-diff`, or `api-processor` can force releases of dependant modules
even when those dependant modules have no direct commits in their own paths.

## Module semantic versioning

For each selected module, the workflow computes the bump level from commit subjects and associated PR titles in the
range after the previous module tag:

- `BREAKING` or `feat!` means `major`;
- `feat` means `minor`;
- `fix` means `patch`;
- no recognised prefix or an unknown prefix also means `patch`.

If multiple matching changes exist, the highest bump wins:

- `major` overrides `minor` and `patch`;
- `minor` overrides `patch`.

For dependant modules selected only because an upstream module changed, but with no direct commits in the module path,
the workflow assigns a `patch` bump. This keeps module tags and global release contents consistent.

## Component release notes

Each component release uses git history as the source of truth.

The release-notes generator for a module compares the previous module tag with the new module tag and collects only the
commits and PRs that affect that module path. The output body is written into the GitHub Release for the module tag.

The generator keeps the core behaviour of the earlier script:

- compare two tags;
- collect commits in the range;
- associate commits with PRs where possible;
- de-duplicate entries by PR;
- classify entries into feature, bugfix, or other sections.

For dependant-only releases with no direct path changes, the notes should state clearly that the release is triggered by
an upstream dependency update.

## Module publish workflow

The existing `.github/workflows/release.yaml` remains the workflow that performs build, package
publish, OCI push, and GitHub Release creation for a module.

It is a reusable workflow (`workflow_call`) so the orchestration workflow can pass `module_id` and
`version` and reuse the generated release-note body via a workflow artifact. The `push` tag trigger
is kept for manual tags. Tag-push runs started by `github-actions[bot]` are skipped so an
orchestration run does not publish the same module twice.

## Global application version

The global release tag format is plain semantic versioning: `X.Y.Z`.

The global bump level is computed from the highest bump among all modules included in the release plan:

- if any released module has a `major` bump, the global release is `major`;
- otherwise, if any released module has a `minor` bump, the global release is `minor`;
- otherwise, the global release is `patch`.

## Global release notes

The global release uses Project/Sprint as the source of truth.

The release-notes generator accepts `sprint_name` as input and adapts the behaviour of
`app-apihub-rns-generator.py`:

- fetch the sprint items from GitHub Project;
- filter them by the selected sprint and the expected completion statuses;
- classify entries into features, bugfixes, and other changes;
- include artefacts for the modules released by this workflow run.

The global release notes should also contain a short `Released modules` section with the module names and their new
versions.

## Implementation shape

The expected implementation has these main parts:

- a new orchestration workflow, `.github/workflows/release-e2e.yaml`;
- `.github/workflows/release.yaml` as a reusable module publish workflow that also still runs on
  manual module tags;
- helper scripts under `tools/ci/` for:
  - release plan calculation;
  - module version calculation;
  - component release-notes generation;
  - global release-notes generation.

Global release notes read GitHub Project data. The default GitHub token cannot always read an
organisation project, so the workflow accepts an optional `GH_PROJECT_TOKEN` secret with
`read:project` access.

## Error handling

The workflow should fail fast when:

- a module tag prefix is missing or invalid;
- semantic version parsing fails for an existing release tag;
- release notes cannot be generated;
- a module tag cannot be created;
- a module release fails to publish;
- the global tag cannot be computed or created.

## Testing and verification

Implementation should be verified with:

- a dry run of the release-plan and version-calculation scripts against a known branch;
- a manual workflow run in `changed` mode;
- a manual workflow run in `all` mode;
- validation that module tags match `{module}/v{semver}`;
- validation that the global tag matches `X.Y.Z`;
- validation that component release notes come from git history;
- validation that global release notes come from the selected sprint.
