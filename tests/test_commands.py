import unittest

from lumina.backend.pacman import (
    PacmanError,
    build_remove_command,
    classify_package,
    parse_query_names,
    parse_sync_list,
)
from lumina.models.package import Origin, Package


class CommandTests(unittest.TestCase):
    def test_remove_command(self) -> None:
        argv = build_remove_command(["vim"], recursive=False, stdbuf=None)
        self.assertEqual(
            argv,
            ["/usr/bin/pkexec", "/usr/bin/pacman", "--color", "never", "-R", "--noconfirm", "vim"],
        )
        recursive = build_remove_command(
            ["vim"],
            recursive=True,
            stdbuf="/usr/bin/stdbuf",
        )
        self.assertEqual(
            recursive,
            [
                "/usr/bin/pkexec",
                "/usr/bin/stdbuf",
                "-oL",
                "-eL",
                "/usr/bin/pacman",
                "--color",
                "never",
                "-Rs",
                "--noconfirm",
                "vim",
            ],
        )

    def test_rejects_invalid_names(self) -> None:
        with self.assertRaises(PacmanError):
            build_remove_command(["-evil"], recursive=False)
        with self.assertRaises(PacmanError):
            build_remove_command([], recursive=False)

    def test_sync_and_query_parsing(self) -> None:
        repos = parse_sync_list(
            "core bash 5.3.20-1 [installed]\n"
            "extra bash 5.3.20-1\n"
            "extra firefox 149.0-1\n"
        )
        self.assertEqual(repos["bash"], "core")
        self.assertEqual(repos["firefox"], "extra")
        self.assertEqual(parse_query_names("bash 5.3.20-1\npython\n"), {"bash", "python"})

    def test_classify(self) -> None:
        foreign = Package(name="yay", version="1")
        official = Package(name="bash", version="1")
        local = Package(name="custom", version="1")
        classify_package(foreign, explicit={"yay"}, foreign={"yay"}, orphans=set(), repos={"yay": "extra"})
        classify_package(official, explicit=set(), foreign=set(), orphans={"bash"}, repos={"bash": "core"})
        classify_package(local, explicit={"custom"}, foreign=set(), orphans=set(), repos={})
        self.assertEqual(foreign.origin, Origin.FOREIGN)
        self.assertIsNone(foreign.repo)
        self.assertTrue(foreign.explicit)
        self.assertEqual(official.origin, Origin.OFFICIAL)
        self.assertEqual(official.repo, "core")
        self.assertTrue(official.orphan)
        self.assertEqual(local.origin, Origin.LOCAL)
