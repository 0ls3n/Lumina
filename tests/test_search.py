import unittest

from lumina.models.package import Origin, Package
from lumina.utils.format import format_count, format_size
from lumina.utils.search import fuzzy_match, package_visible


class SearchTests(unittest.TestCase):
    def test_fuzzy_and_filters(self) -> None:
        self.assertTrue(fuzzy_match("bsh", "bash"))
        self.assertFalse(fuzzy_match("zzz", "bash"))
        official = Package(name="bash", version="1", description="shell", origin=Origin.OFFICIAL, explicit=False)
        foreign = Package(name="yay-bin", version="1", description="AUR helper", origin=Origin.FOREIGN, explicit=True)
        orphan = Package(name="left", version="1", origin=Origin.OFFICIAL, orphan=True)
        self.assertTrue(package_visible(official, "gnu", "all") or package_visible(official, "sh", "all"))
        self.assertTrue(package_visible(official, "bsh", "official"))
        self.assertFalse(package_visible(official, "", "explicit"))
        self.assertTrue(package_visible(foreign, "helper", "foreign"))
        self.assertFalse(package_visible(foreign, "", "official"))
        self.assertTrue(package_visible(orphan, "", "orphans"))
        self.assertFalse(package_visible(official, "", "orphans"))
        app = Package(name="godot", version="1", app_name="Godot")
        library = Package(name="glibc", version="1")
        self.assertTrue(package_visible(app, "", "apps"))
        self.assertTrue(package_visible(app, "gdt", "apps"))
        self.assertFalse(package_visible(library, "", "apps"))

    def test_format(self) -> None:
        self.assertEqual(format_size(None), "—")
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(1024), "1.00 KiB")
        self.assertEqual(format_count(2, 2), "2 packages")
        self.assertEqual(format_count(1, 4), "1 of 4 packages")
