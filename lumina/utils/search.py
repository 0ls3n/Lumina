from lumina.models.package import Origin, Package


def fuzzy_match(query: str, text: str) -> bool:
    needle = query.strip().casefold()
    if not needle:
        return True
    haystack = text.casefold()
    if needle in haystack:
        return True
    index = 0
    for char in haystack:
        if char == needle[index]:
            index += 1
            if index == len(needle):
                return True
    return False


def matches_query(name: str, description: str, query: str, app_name: str = "") -> bool:
    text = query.strip()
    if not text:
        return True
    folded = text.casefold()
    if folded in description.casefold() or folded in app_name.casefold():
        return True
    return fuzzy_match(text, name) or fuzzy_match(text, app_name)


def package_visible(package: Package, query: str, mode: str) -> bool:
    if mode == "apps" and not package.app_name:
        return False
    if mode == "explicit" and not package.explicit:
        return False
    if mode == "official" and package.origin is not Origin.OFFICIAL:
        return False
    if mode == "foreign" and package.origin not in (Origin.FOREIGN, Origin.AUR):
        return False
    if mode == "orphans" and not package.orphan:
        return False
    return matches_query(package.name, package.description, query, package.app_name)
