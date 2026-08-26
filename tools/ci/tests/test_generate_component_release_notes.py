import unittest

from tools.ci.generate_component_release_notes import (
    classify_section,
    render_component_notes,
    render_dependent_only_notes,
)


class ComponentReleaseNotesTests(unittest.TestCase):
    def test_classify_section_uses_major_minor_patch_mapping(self):
        self.assertEqual(classify_section("feat: add panel"), "Features")
        self.assertEqual(classify_section("feat!: break panel"), "Features")
        self.assertEqual(classify_section("fix: repair panel"), "Bugfixes")
        self.assertEqual(classify_section("docs: update"), "Other")

    def test_render_dependent_only_notes_mentions_upstream(self):
        body = render_dependent_only_notes("ui", "api-processor", "1.4.0")
        self.assertIn("upstream dependency update", body)
        self.assertIn("api-processor", body)
        self.assertIn("1.4.0", body)

    def test_render_component_notes_groups_entries(self):
        body = render_component_notes(
            module_id="backend",
            version="1.4.0",
            previous_tag="backend/v1.3.0",
            next_tag="backend/v1.4.0",
            image="ghcr.io/netcracker/qubership-apihub-backend",
            entries=[
                {"section": "Features", "line": "- feat: add search by @alice in https://example/pr/1"},
                {"section": "Bugfixes", "line": "- fix: repair login by @bob in https://example/pr/2"},
            ],
            dependency_changes="No dependency changes.",
        )
        self.assertIn("backend/v1.4.0", body)
        self.assertIn("ghcr.io/netcracker/qubership-apihub-backend:1.4.0", body)
        self.assertIn("feat: add search", body)
        self.assertIn("fix: repair login", body)
        self.assertIn("backend/v1.3.0...backend/v1.4.0", body)


if __name__ == "__main__":
    unittest.main()
