# End-to-end release workflow implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a manual GitHub Actions release workflow that computes module versions, creates module and global tags, generates module and global release notes, and publishes only the required releases.

**Architecture:** Keep `.github/workflows/release.yaml` as the tag-driven module publish workflow, then add a new orchestration workflow that computes a release plan and creates the tags in the right order. Move release-planning and release-notes logic into focused Python helpers under `tools/ci/` so GitHub Actions YAML stays small and the release rules remain testable.

**Tech Stack:** GitHub Actions, Python 3, PyYAML, GitHub REST and GraphQL APIs, existing monorepo module metadata in `tools/modules.yaml`

## Global Constraints

- Global release workflow uses `workflow_dispatch`.
- Workflow inputs are `sprint_name` and `release_mode`.
- `release_mode` supports `changed` and `all`.
- Component release notes use git history as the source of truth.
- Global release notes use Project/Sprint as the source of truth.
- Component semantic versioning rules are: `BREAKING` or `feat!` -> major, `feat` -> minor, `fix` -> patch, unknown or missing prefix -> patch.
- Dependant modules from `tools/modules.yaml` are included transitively when an upstream module is selected.
- Dependant-only releases with no direct commits receive a `patch` bump.
- Module tags follow `{module}/v{semver}`.
- Global tags follow `X.Y.Z`.

---

### Task 1: Add release plan generator

**Files:**
- Create: `tools/ci/compute_release_plan.py`
- Test: `tools/ci/tests/test_compute_release_plan.py`

**Interfaces:**
- Consumes: `tools/modules.yaml`, local git tags and history
- Produces: `compute_release_plan.py --release-mode <changed|all> --output json` -> JSON object with `modules`, `released_modules`, `global_bump`, `reasons`

- [ ] **Step 1: Write the failing tests**

```python
import unittest

from tools.ci.compute_release_plan import classify_bump, expand_dependants, highest_bump


class ReleasePlanTests(unittest.TestCase):
    def test_classify_bump_returns_major_for_breaking(self):
        self.assertEqual(classify_bump("feat!: break API"), "major")
        self.assertEqual(classify_bump("BREAKING: remove field"), "major")

    def test_classify_bump_returns_minor_for_feat(self):
        self.assertEqual(classify_bump("feat: add endpoint"), "minor")

    def test_classify_bump_returns_patch_for_fix_and_unknown(self):
        self.assertEqual(classify_bump("fix: repair login"), "patch")
        self.assertEqual(classify_bump("docs: update readme"), "patch")
        self.assertEqual(classify_bump("plain message"), "patch")

    def test_highest_bump_prefers_major_then_minor_then_patch(self):
        self.assertEqual(highest_bump(["patch", "minor"]), "minor")
        self.assertEqual(highest_bump(["patch", "major"]), "major")

    def test_expand_dependants_adds_transitive_dependants(self):
        modules = {
            "commons-go": {"dependents": ["backend", "linter"]},
            "backend": {"dependents": ["ui"]},
            "linter": {"dependents": []},
            "ui": {"dependents": []},
        }
        self.assertEqual(
            expand_dependants(modules, {"commons-go"}),
            {"commons-go", "backend", "linter", "ui"},
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -3 -m unittest tools.ci.tests.test_compute_release_plan -v`  
Expected: FAIL because `tools.ci.compute_release_plan` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
from __future__ import annotations

from typing import Iterable


def classify_bump(message: str) -> str:
    lowered = message.strip().lower()
    if lowered.startswith("breaking") or lowered.startswith("feat!"):
        return "major"
    if lowered.startswith("feat"):
        return "minor"
    return "patch"


def highest_bump(levels: Iterable[str]) -> str:
    levels = list(levels)
    if "major" in levels:
        return "major"
    if "minor" in levels:
        return "minor"
    return "patch"


def expand_dependants(modules_cfg: dict, seeds: set[str]) -> set[str]:
    result = set(seeds)
    queue = list(seeds)
    while queue:
        current = queue.pop(0)
        for dep in modules_cfg.get(current, {}).get("dependents", []) or []:
            if dep not in result:
                result.add(dep)
                queue.append(dep)
    return result
```

- [ ] **Step 4: Extend the implementation to produce the release plan**

```python
def build_release_plan(release_mode: str) -> dict:
    """
    Return:
    {
      "modules": [{"module_id": "backend", "next_tag": "backend/v1.2.3", ...}],
      "released_modules": ["backend", "ui"],
      "global_bump": "minor",
      "reasons": {"ui": "dependent of api-processor"}
    }
    """
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `py -3 -m unittest tools.ci.tests.test_compute_release_plan -v`  
Expected: PASS

### Task 2: Add component release-notes generator

**Files:**
- Create: `tools/ci/generate_component_release_notes.py`
- Test: `tools/ci/tests/test_generate_component_release_notes.py`

**Interfaces:**
- Consumes: repository git history, module metadata, previous and next module tags
- Produces: Markdown release body for a module

- [ ] **Step 1: Write the failing tests**

```python
import unittest

from tools.ci.generate_component_release_notes import (
    classify_section,
    render_dependent_only_notes,
)


class ComponentReleaseNotesTests(unittest.TestCase):
    def test_classify_section_uses_major_minor_patch_mapping(self):
        self.assertEqual(classify_section("feat: add panel"), "Features")
        self.assertEqual(classify_section("fix: repair panel"), "Bugfixes")
        self.assertEqual(classify_section("docs: update"), "Other")

    def test_render_dependent_only_notes_mentions_upstream(self):
        body = render_dependent_only_notes("ui", "api-processor", "1.4.0")
        self.assertIn("upstream dependency update", body)
        self.assertIn("api-processor", body)
        self.assertIn("1.4.0", body)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -3 -m unittest tools.ci.tests.test_generate_component_release_notes -v`  
Expected: FAIL because the generator file does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
def classify_section(message: str) -> str:
    lowered = message.strip().lower()
    if lowered.startswith("feat"):
        return "Features"
    if lowered.startswith("fix"):
        return "Bugfixes"
    return "Other"


def render_dependent_only_notes(module_id: str, upstream_module: str, upstream_version: str) -> str:
    return (
        f"# {module_id}\n\n"
        "## Changed\n\n"
        f"- Release triggered by an upstream dependency update in `{upstream_module}` to `{upstream_version}`.\n"
    )
```

- [ ] **Step 4: Extend the implementation to gather PR and commit data**

```python
def generate_release_notes(module_id: str, previous_tag: str, next_tag: str, module_path: str) -> str:
    """
    Compare tags, collect commits for module_path, map commits to PRs, de-duplicate PR entries,
    then return Markdown sections for features, bugfixes, and other changes.
    """
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `py -3 -m unittest tools.ci.tests.test_generate_component_release_notes -v`  
Expected: PASS

### Task 3: Add global release-notes generator

**Files:**
- Create: `tools/ci/generate_global_release_notes.py`
- Test: `tools/ci/tests/test_generate_global_release_notes.py`

**Interfaces:**
- Consumes: `sprint_name`, released module versions, GitHub Project data
- Produces: Markdown release body for the global `X.Y.Z` tag

- [ ] **Step 1: Write the failing tests**

```python
import unittest

from tools.ci.generate_global_release_notes import (
    build_released_modules_section,
    compute_next_global_version,
)


class GlobalReleaseNotesTests(unittest.TestCase):
    def test_compute_next_global_version_uses_highest_bump(self):
        self.assertEqual(compute_next_global_version("1.2.3", ["patch"]), "1.2.4")
        self.assertEqual(compute_next_global_version("1.2.3", ["minor"]), "1.3.0")
        self.assertEqual(compute_next_global_version("1.2.3", ["major"]), "2.0.0")

    def test_build_released_modules_section_lists_versions(self):
        text = build_released_modules_section({"backend": "1.4.0", "ui": "2.1.3"})
        self.assertIn("backend", text)
        self.assertIn("1.4.0", text)
        self.assertIn("ui", text)
        self.assertIn("2.1.3", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -3 -m unittest tools.ci.tests.test_generate_global_release_notes -v`  
Expected: FAIL because the generator file does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
from packaging.version import Version


def compute_next_global_version(previous_version: str, bumps: list[str]) -> str:
    version = Version(previous_version)
    if "major" in bumps:
        return f"{version.major + 1}.0.0"
    if "minor" in bumps:
        return f"{version.major}.{version.minor + 1}.0"
    return f"{version.major}.{version.minor}.{version.micro + 1}"


def build_released_modules_section(released_modules: dict[str, str]) -> str:
    lines = ["## Released modules", ""]
    for module_id, version in released_modules.items():
        lines.append(f"- `{module_id}` -> `{version}`")
    return "\n".join(lines)
```

- [ ] **Step 4: Extend the implementation to call GitHub Project and render the full release body**

```python
def generate_global_release_notes(sprint_name: str, released_modules: dict[str, str]) -> str:
    """
    Query GitHub Project items for sprint_name, classify them into sections, add released module
    artefacts, then return the full Markdown release body.
    """
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `py -3 -m unittest tools.ci.tests.test_generate_global_release_notes -v`  
Expected: PASS

### Task 4: Wire the workflows

**Files:**
- Create: `.github/workflows/release-e2e.yaml`
- Modify: `.github/workflows/release.yaml`

**Interfaces:**
- Consumes: JSON release plan and generated Markdown release-note bodies
- Produces: module tags, module releases, global tag, global release

- [ ] **Step 1: Add orchestration workflow inputs and plan step**

```yaml
on:
  workflow_dispatch:
    inputs:
      sprint_name:
        description: Sprint name for global release notes
        required: true
        type: string
      release_mode:
        description: Release changed modules only or all modules
        required: true
        type: choice
        options:
          - changed
          - all
```

- [ ] **Step 2: Add jobs that compute the plan and create module tags**

```yaml
jobs:
  compute-plan:
    runs-on: ubuntu-latest
    outputs:
      plan: ${{ steps.plan.outputs.plan }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - id: plan
        run: |
          python3 tools/ci/compute_release_plan.py \
            --release-mode "${{ github.event.inputs.release_mode }}" \
            > release-plan.json
          echo "plan=$(jq -c . release-plan.json)" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 3: Update the module release workflow to use generated release notes**

```yaml
- name: GitHub Release
  uses: softprops/action-gh-release@v2
  with:
    tag_name: ${{ github.ref_name }}
    body_path: release-notes.md
```

- [ ] **Step 4: Add global tag and global release creation**

```yaml
  create-global-release:
    needs: create-module-tags
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: |
          python3 tools/ci/generate_global_release_notes.py \
            --sprint-name "${{ github.event.inputs.sprint_name }}" \
            --released-modules-file released-modules.json \
            --output global-release-notes.md
          git tag "${NEXT_GLOBAL_VERSION}"
          git push origin "${NEXT_GLOBAL_VERSION}"
          gh release create "${NEXT_GLOBAL_VERSION}" --notes-file global-release-notes.md
```

- [ ] **Step 5: Validate the workflow YAML**

Run: `git diff -- .github/workflows/release.yaml .github/workflows/release-e2e.yaml`  
Expected: orchestration workflow exists and module release workflow accepts generated notes

### Task 5: Run verification

**Files:**
- Verify: `tools/ci/compute_release_plan.py`
- Verify: `tools/ci/generate_component_release_notes.py`
- Verify: `tools/ci/generate_global_release_notes.py`
- Verify: `.github/workflows/release.yaml`
- Verify: `.github/workflows/release-e2e.yaml`

**Interfaces:**
- Consumes: the completed implementation
- Produces: evidence that tests and basic script execution succeed

- [ ] **Step 1: Run Python unit tests**

```bash
py -3 -m unittest \
  tools.ci.tests.test_compute_release_plan \
  tools.ci.tests.test_generate_component_release_notes \
  tools.ci.tests.test_generate_global_release_notes -v
```

- [ ] **Step 2: Run a dry plan generation**

```bash
py -3 tools/ci/compute_release_plan.py --release-mode changed
```

- [ ] **Step 3: Lint edited files with repository tooling if available**

```bash
git diff -- .github/workflows/release.yaml .github/workflows/release-e2e.yaml tools/ci
```

- [ ] **Step 4: Review requirements against the spec**

```text
Confirm workflow_dispatch inputs, module semver rules, dependent expansion, component notes source,
global sprint source, module tags, and global tag format.
```
