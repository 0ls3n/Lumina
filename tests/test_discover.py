import unittest

from pathlib import Path
import tempfile

from lumina.backend.appicons import build_index
from lumina.backend.discover import AUR_APPS, CATEGORIES, catalog_names
from lumina.backend.pacman import validate_package_names


class DiscoverCatalogTests(unittest.TestCase):
    def test_catalog_names_are_valid(self) -> None:
        names = catalog_names()
        self.assertIn("firefox", names)
        self.assertIn("godot", names)
        validate_package_names(names)
        validate_package_names([name for name, *_rest in AUR_APPS])

    def test_categories_start_with_popular(self) -> None:
        self.assertEqual(CATEGORIES[0][0], "popular")
        self.assertGreaterEqual(len(CATEGORIES[0][2]), 8)
        ids = [section[0] for section in CATEGORIES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_icon_index_maps_package_and_icon_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            icon = root / "128x128" / "gimp_gimp.jxl"
            other = root / "128x128" / "obs-studio_com.obsproject.Studio.jxl"
            icon.parent.mkdir()
            icon.write_bytes(b"jxl")
            other.write_bytes(b"jxl")
            index = build_index(root)
            self.assertEqual(index["by_package"]["gimp"], str(icon))
            self.assertEqual(index["by_icon"]["com.obsproject.Studio"], str(other))
            self.assertEqual(index["by_package"]["obs-studio"], str(other))
