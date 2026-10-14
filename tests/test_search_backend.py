import unittest

from lumina.backend.pacman import PacmanError
from lumina.backend.search import clean_query, install_command, parse_search_output

SAMPLE = """
extra/godot 4.7.2-2 [installed]
    Advanced cross-platform 2D and 3D game engine
aur/godot-bin 4.7-1 (+10 0.50)
    Binary release of Godot
extra/firefox 149.0-1
    Fast, Private & Safe Web Browser
"""


class SearchBackendTests(unittest.TestCase):
    def test_parse_search_output(self) -> None:
        results = parse_search_output(SAMPLE, "official")
        self.assertEqual([item.name for item in results], ["godot", "godot-bin", "firefox"])
        godot, binary, firefox = results
        self.assertTrue(godot.installed)
        self.assertEqual(godot.repo, "extra")
        self.assertEqual(godot.source, "official")
        self.assertEqual(godot.description, "Advanced cross-platform 2D and 3D game engine")
        self.assertEqual(binary.source, "aur")
        self.assertFalse(binary.installed)
        self.assertEqual(binary.version, "4.7-1")
        self.assertFalse(firefox.installed)

    def test_clean_query(self) -> None:
        self.assertEqual(clean_query("  godot  "), "godot")
        with self.assertRaises(PacmanError):
            clean_query("-Syu")
        with self.assertRaises(PacmanError):
            clean_query("foo;rm")

    def test_install_command(self) -> None:
        argv = install_command("vim", "official")
        self.assertIn("-S", argv)
        self.assertIn("vim", argv)
        self.assertTrue(any(part.endswith("pkexec") for part in argv))
        with self.assertRaises(PacmanError):
            install_command("-evil", "official")
