import unittest

from tools.ci.generate_global_release_notes import (
    build_released_modules_section,
    compute_next_global_version,
    render_global_release_notes,
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

    def test_render_global_release_notes_includes_sprint_and_modules(self):
        body = render_global_release_notes(
            version="1.5.0",
            sprint_name="APIHUB-26.3.1",
            released_modules={"backend": "1.4.0", "ui": "2.1.3"},
            images=[
                "ghcr.io/netcracker/qubership-apihub-backend:1.4.0",
                "ghcr.io/netcracker/qubership-apihub-ui:2.1.3",
            ],
            features=["| Issue: <https://example/1> | Add search | @alice | |"],
            bugfixes=[],
            other=[],
        )
        self.assertIn("1.5.0", body)
        self.assertIn("APIHUB-26.3.1", body)
        self.assertIn("Released modules", body)
        self.assertIn("backend", body)
        self.assertIn("Add search", body)
        self.assertIn("_No bugfixes this release._", body)


if __name__ == "__main__":
    unittest.main()
