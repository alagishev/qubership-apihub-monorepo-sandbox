import unittest

from tools.ci.compute_release_plan import (
    bump_version,
    classify_bump,
    expand_dependants,
    highest_bump,
    latest_matching_tag,
    topological_release_order,
)


class ReleasePlanTests(unittest.TestCase):
    def test_classify_bump_returns_major_for_breaking(self):
        self.assertEqual(classify_bump("feat!: break API"), "major")
        self.assertEqual(classify_bump("BREAKING: remove field"), "major")
        self.assertEqual(classify_bump("feat(api)!: drop field"), "major")

    def test_classify_bump_returns_minor_for_feat(self):
        self.assertEqual(classify_bump("feat: add endpoint"), "minor")
        self.assertEqual(classify_bump("feat(ui): add panel"), "minor")

    def test_classify_bump_returns_patch_for_fix_and_unknown(self):
        self.assertEqual(classify_bump("fix: repair login"), "patch")
        self.assertEqual(classify_bump("docs: update readme"), "patch")
        self.assertEqual(classify_bump("plain message"), "patch")

    def test_highest_bump_prefers_major_then_minor_then_patch(self):
        self.assertEqual(highest_bump(["patch", "minor"]), "minor")
        self.assertEqual(highest_bump(["patch", "major"]), "major")
        self.assertEqual(highest_bump([]), "patch")

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

    def test_bump_version_from_existing_and_initial(self):
        self.assertEqual(bump_version("1.2.3", "patch"), "1.2.4")
        self.assertEqual(bump_version("1.2.3", "minor"), "1.3.0")
        self.assertEqual(bump_version("1.2.3", "major"), "2.0.0")
        self.assertEqual(bump_version(None, "patch"), "0.0.1")
        self.assertEqual(bump_version(None, "minor"), "0.1.0")
        self.assertEqual(bump_version(None, "major"), "1.0.0")

    def test_latest_matching_tag_picks_highest_semver(self):
        tags = ["backend/v1.2.0", "backend/v1.10.0", "ui/v9.0.0", "backend/v1.9.1"]
        self.assertEqual(latest_matching_tag(tags, "backend/v"), "backend/v1.10.0")
        self.assertIsNone(latest_matching_tag(tags, "linter/v"))

    def test_topological_release_order_puts_upstreams_first(self):
        modules = {
            "api-diff": {"dependents": ["api-processor"]},
            "api-processor": {"dependents": ["ui", "build-task-consumer"]},
            "ui": {"dependents": []},
            "build-task-consumer": {"dependents": []},
        }
        order = topological_release_order(
            modules, ["ui", "api-diff", "build-task-consumer", "api-processor"]
        )
        self.assertLess(order.index("api-diff"), order.index("api-processor"))
        self.assertLess(order.index("api-processor"), order.index("ui"))
        self.assertLess(order.index("api-processor"), order.index("build-task-consumer"))

    def test_build_release_plan_changed_mode_includes_dependants(self):
        from tools.ci.compute_release_plan import build_release_plan

        class FakeGit:
            def path_has_changes(self, previous_tag, module_path):
                return module_path == "qubership-apihub-commons-go"

            def commit_subjects(self, previous_tag, module_path):
                if module_path == "qubership-apihub-commons-go":
                    return ["feat: add helper"]
                return []

        modules = {
            "commons-go": {
                "path": "qubership-apihub-commons-go",
                "release_tag": "commons-go/v",
                "dependents": ["backend"],
                "kind": "go-lib",
            },
            "backend": {
                "path": "qubership-apihub-backend",
                "release_tag": "backend/v",
                "dependents": [],
                "kind": "go-service",
                "image": "ghcr.io/netcracker/qubership-apihub-backend",
            },
            "ui": {
                "path": "qubership-apihub-ui",
                "release_tag": "ui/v",
                "dependents": [],
                "kind": "npm-ui",
            },
        }
        tags = ["commons-go/v1.0.0", "backend/v2.0.0", "ui/v3.0.0", "1.4.0"]
        plan = build_release_plan("changed", modules, tags, FakeGit())
        self.assertEqual(plan["released_modules"]["commons-go"], "1.1.0")
        self.assertEqual(plan["released_modules"]["backend"], "2.0.1")
        self.assertNotIn("ui", plan["released_modules"])
        self.assertEqual(plan["reasons"]["backend"], "dependent of commons-go")
        self.assertEqual(plan["global_bump"], "minor")
        self.assertEqual(plan["next_global_version"], "1.5.0")
        self.assertEqual([item["module_id"] for item in plan["modules"]], ["commons-go", "backend"])

    def test_build_release_plan_uses_global_tag_when_module_tag_missing(self):
        from tools.ci.compute_release_plan import build_release_plan

        class FakeGit:
            def path_has_changes(self, previous_tag, module_path):
                self.last_compare = previous_tag
                return module_path == "qubership-apihub-backend"

            def commit_subjects(self, previous_tag, module_path):
                if module_path == "qubership-apihub-backend":
                    return ["fix: repair login"]
                return []

        modules = {
            "backend": {
                "path": "qubership-apihub-backend",
                "release_tag": "backend/v",
                "dependents": [],
                "kind": "go-service",
            },
            "ui": {
                "path": "qubership-apihub-ui",
                "release_tag": "ui/v",
                "dependents": [],
                "kind": "npm-ui",
            },
        }
        git = FakeGit()
        plan = build_release_plan("changed", modules, ["2.13.0"], git)
        self.assertEqual(git.last_compare, "2.13.0")
        self.assertEqual(plan["released_modules"], {"backend": "0.0.1"})
        self.assertEqual(plan["modules"][0]["compare_ref"], "2.13.0")
        self.assertEqual(plan["next_global_version"], "2.13.1")


if __name__ == "__main__":
    unittest.main()
