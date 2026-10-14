import shutil

HELPER_CANDIDATES = ("paru", "yay")


def detect_helper() -> str | None:
    for name in HELPER_CANDIDATES:
        if shutil.which(name):
            return name
    return None


def helper_status() -> str:
    helper = detect_helper()
    if helper:
        return f"AUR helper: {helper}"
    return "No AUR helper found"
