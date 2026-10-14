import sys

try:
    from lumina.main import main
except ImportError as exc:
    print(
        "Lumina needs Python, PyGObject, GTK4, and libadwaita.\n"
        f"Import failed: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


if __name__ == "__main__":
    raise SystemExit(main())
