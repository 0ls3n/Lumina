import unittest
from datetime import datetime
from pathlib import Path

from lumina.backend.parser import parse_pacman_date, parse_packages, parse_size

FIXTURE = Path(__file__).parent / "fixtures" / "pacman_qi.txt"


class ParserTests(unittest.TestCase):
    def test_parse_fixture(self) -> None:
        packages = parse_packages(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([package.name for package in packages], ["bash", "python"])
        bash, python = packages
        self.assertEqual(bash.version, "5.3.20-1")
        self.assertEqual(bash.depends, ["readline", "glibc", "ncurses"])
        self.assertEqual(bash.required_by, ["pacman", "systemd"])
        self.assertEqual(bash.optional_deps, ["bash-completion: for tab completion"])
        self.assertFalse(bash.explicit)
        self.assertEqual(bash.licenses, ["GPL-3.0-or-later"])
        self.assertEqual(bash.installed_size, int(9.59 * 1024 * 1024))
        self.assertEqual(bash.install_date, datetime(2026, 10, 7, 15, 33, 42))
        self.assertEqual(python.optional_deps[1], "python-pip: for installing packages")
        self.assertTrue(python.explicit)
        self.assertEqual(python.replaces, ["python3"])
        self.assertEqual(python.groups, [])

    def test_size_and_date_edges(self) -> None:
        self.assertIsNone(parse_size("None"))
        self.assertIsNone(parse_size(""))
        self.assertEqual(parse_size("512 B"), 512)
        self.assertIsNone(parse_pacman_date("not a date"))
        self.assertEqual(parse_pacman_date("Fri Oct 2 12:23:31 2026"), datetime(2026, 10, 2, 12, 23, 31))
