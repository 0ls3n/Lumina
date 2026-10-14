import tempfile
import unittest
from pathlib import Path

from lumina.backend.apps import discover_applications, launchable_name, pick_app_name


class AppDiscoveryTests(unittest.TestCase):
    def test_launchable_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            visible = root / "godot.desktop"
            visible.write_text(
                "[Desktop Entry]\nName=Godot\nType=Application\n",
                encoding="utf-8",
            )
            hidden = root / "hidden.desktop"
            hidden.write_text(
                "[Desktop Entry]\nName=Hidden\nType=Application\nNoDisplay=true\n",
                encoding="utf-8",
            )
            link = root / "link.desktop"
            link.write_text("[Desktop Entry]\nName=Link\nType=Link\n", encoding="utf-8")
            self.assertEqual(launchable_name(visible), "Godot")
            self.assertIsNone(launchable_name(hidden))
            self.assertIsNone(launchable_name(link))

    def test_discover_applications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            desktop_dir = root / "usr" / "share" / "applications"
            desktop_dir.mkdir(parents=True)
            (desktop_dir / "org.godotengine.Godot.desktop").write_text(
                "[Desktop Entry]\nName=Godot Engine\nIcon=godot\nType=Application\n",
                encoding="utf-8",
            )
            (desktop_dir / "helper.desktop").write_text(
                "[Desktop Entry]\nName=Helper\nType=Application\nHidden=true\n",
                encoding="utf-8",
            )
            entry = root / "db" / "godot-4.7.2-2"
            entry.mkdir(parents=True)
            (entry / "desc").write_text("%NAME%\ngodot\n", encoding="utf-8")
            (entry / "files").write_text(
                "\n".join(
                    [
                        "usr/share/applications/",
                        "usr/share/applications/org.godotengine.Godot.desktop",
                        "usr/share/applications/helper.desktop",
                    ]
                ),
                encoding="utf-8",
            )
            library = root / "db" / "glibc-2.0-1"
            library.mkdir()
            (library / "desc").write_text("%NAME%\nglibc\n", encoding="utf-8")
            (library / "files").write_text("usr/lib/libc.so\n", encoding="utf-8")
            apps = discover_applications(root / "db", root)
            self.assertEqual(set(apps), {"godot"})
            self.assertEqual(apps["godot"].name, "Godot Engine")
            self.assertEqual(apps["godot"].icon, "godot")

    def test_pick_app_name(self) -> None:
        self.assertEqual(pick_app_name("godot", ["Godot Engine", "Godot"]), "Godot")
        self.assertEqual(pick_app_name("code", ["Visual Studio Code"]), "Visual Studio Code")
