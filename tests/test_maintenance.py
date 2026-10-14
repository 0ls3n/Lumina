import unittest

from lumina.backend.maintenance import (
    DiskReport,
    cache_usage,
    clean_all_cache_command,
    clean_unused_cache_command,
    disk_segments,
    parse_orphans,
    remove_orphans_command,
)
from lumina.backend.pacman import PacmanError


class MaintenanceTests(unittest.TestCase):
    def test_parse_orphans(self) -> None:
        orphans = parse_orphans("cli11 2.7.2-1\ncython 3.3.0-2\n\n")
        self.assertEqual([(item.name, item.version) for item in orphans], [("cli11", "2.7.2-1"), ("cython", "3.3.0-2")])

    def test_cache_usage(self) -> None:
        files = [
            ("firefox-1.0-1-x86_64.pkg.tar.zst", 100),
            ("firefox-1.0-1-x86_64.pkg.tar.zst.sig", 10),
            ("firefox-0.9-1-x86_64.pkg.tar.zst", 80),
            ("oldpkg-2-1-x86_64.pkg.tar.zst", 40),
        ]
        total, unused, count, unused_count = cache_usage(files, [("firefox", "1.0-1")])
        self.assertEqual(total, 230)
        self.assertEqual(unused, 120)
        self.assertEqual(count, 4)
        self.assertEqual(unused_count, 2)

    def test_disk_segments(self) -> None:
        report = DiskReport("/", 1000, 400, 200, 150, 50, True)
        self.assertEqual(
            disk_segments(report),
            [("apps", 200), ("files", 150), ("cache", 50), ("other", 200), ("free", 400)],
        )
        overflow = DiskReport("/", 100, 40, 80, 50, 20, True)
        names = [name for name, _amount in disk_segments(overflow)]
        amounts = [amount for _name, amount in disk_segments(overflow)]
        self.assertEqual(names, ["apps", "files", "cache", "other", "free"])
        self.assertEqual(sum(amounts[:4]), 60)
        self.assertEqual(amounts[-1], 40)

    def test_commands(self) -> None:
        remove = remove_orphans_command(["cli11"])
        self.assertIn("-Rns", remove)
        self.assertIn("cli11", remove)
        self.assertIn("-Sc", clean_unused_cache_command())
        self.assertIn("-Scc", clean_all_cache_command())
        with self.assertRaises(PacmanError):
            remove_orphans_command(["-evil"])
