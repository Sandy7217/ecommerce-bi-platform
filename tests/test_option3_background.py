from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LoginBackgroundTest(unittest.TestCase):
    def test_login_background_is_generic_and_dashboard_layout_is_unchanged(self) -> None:
        auth_layout = ROOT / "frontend" / "app" / "(auth)" / "layout.tsx"
        dashboard_layout = ROOT / "frontend" / "app" / "(dashboard)" / "layout.tsx"
        globals_css = ROOT / "frontend" / "app" / "globals.css"

        self.assertIn("login-option3-bg", auth_layout.read_text())
        self.assertIn('className="min-h-screen bg-canvas"', dashboard_layout.read_text())

        css = globals_css.read_text()
        self.assertIn(".login-option3-bg", css)
        self.assertNotIn(".png", css.lower())
        self.assertNotIn("commerceDrift", css)


if __name__ == "__main__":
    unittest.main()
