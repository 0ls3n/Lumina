import unittest

from lumina.backend.pacman import PacmanError
from lumina.backend.updates import (
    PendingUpdate,
    package_update_command,
    parse_upgrades,
    strip_ansi,
    sync_command,
    system_update_command,
)


class UpdateTests(unittest.TestCase):
    def test_parse_upgrades(self) -> None:
        text = "uv 0.13.0-1 -> 0.13.1-1\nnot an update\n\x1b[1mfirefox 1-1 -> 2-1\x1b[0m\n"
        updates = parse_upgrades(strip_ansi(text), "official")
        self.assertEqual(
            updates,
            [
                PendingUpdate("uv", "0.13.0-1", "0.13.1-1", "official"),
                PendingUpdate("firefox", "1-1", "2-1", "official"),
            ],
        )
        self.assertEqual(parse_upgrades("", "aur"), [])

    def test_commands(self) -> None:
        system = system_update_command()
        self.assertIn("-Syu", system)
        self.assertIn("--noconfirm", system)
        self.assertTrue(system[0].endswith("stdbuf") or system[0].endswith("pkexec") or system[0].endswith("yay") or system[0].endswith("paru"))
        official = package_update_command(PendingUpdate("vim", "1", "2", "official"))
        self.assertIn("-S", official)
        self.assertIn("vim", official)
        self.assertTrue(any(part.endswith("pkexec") for part in official))
        synced = sync_command()
        self.assertIn("-Sy", synced)
        self.assertNotIn("-Syu", synced)
        with self.assertRaises(PacmanError):
            package_update_command(PendingUpdate("-evil", "1", "2", "official"))
