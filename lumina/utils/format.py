def format_size(size: int | None) -> str:
    if size is None:
        return "—"
    value = float(size)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return "—"


def format_count(shown: int, total: int) -> str:
    if shown == total:
        noun = "package" if total == 1 else "packages"
        return f"{total:,} {noun}"
    return f"{shown:,} of {total:,} packages"
