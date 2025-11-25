from __future__ import annotations

import functools
import pathlib


PYCONIFY_TO_PREFIXES = {
    "mdi": "material",
    "simple-icons": "simple",
    "octicon": "octicons",
    "fa6-regular": "fontawesome-regular",
    "fa-brands": "fontawesome-brands",
    "fa6-solid": "fontawesome-solid",
}


ROOT = pathlib.Path(__file__).parent
ICON_FILE = ROOT / "resources" / "icons.json.gzip"


@functools.cache
def _get_collection_map(*prefixes: str) -> dict[str, list[str]]:
    """Return a dictionary with a mapping from pyconify name to icon prefixes.

    In order to provide compatibility with the materialx-icon-index,
    we also add the prefixes used by that index, which is different from
    the pyconify prefixes. (material vs mdi etc, see PYCONIFY_TO_PREFIXES)

    Args:
        prefixes: The collections to fetch
    """
    import pyconify

    mapping = {coll: [coll] for coll in pyconify.collections(*prefixes)}
    for k, v in PYCONIFY_TO_PREFIXES.items():
        if k in mapping:
            mapping[k].append(v)
    return mapping


@functools.cache
def _get_pyconify_icon_index(*collections: str) -> dict[str, dict[str, str]]:
    """Return a icon index for the pymdownx emoji extension containing pyconify icons.

    The dictionaries contain three key-value pairs:
    - "name": the emoji identifier
    - "path": the pyconify key
    - "set": the collection name

    Args:
        collections: Collections to fetch. If none given, fetch all
    """
    import pyconify

    index = {}
    for coll, prefixes in _get_collection_map(*collections).items():
        collection = pyconify.collection(coll)
        for icon_name in collection.get("uncategorized", []):
            for prefix in prefixes:
                name = f":{prefix}-{icon_name}:"
                index[name] = {
                    "name": name,
                    "path": f"{coll}:{icon_name}",
                    "set": coll,
                }
        for cat in pyconify.collection(coll).get("categories", {}).values():
            for icon_name in cat:
                for prefix in prefixes:
                    name = f":{prefix}-{icon_name}:"
                    index[name] = {
                        "name": name,
                        "path": f"{coll}:{icon_name}",
                        "set": coll,
                    }
    return index


def write_icon_index() -> None:
    """Fetch the complete icon index and write it gzipped to disk."""
    import gzip
    import json

    mapping = _get_pyconify_icon_index()
    with gzip.open(ICON_FILE, "w") as file:
        file.write(json.dumps(mapping).encode())


def load_icon_index() -> dict[str, dict[str, str]]:
    """Load the complete icon index from disk."""
    import gzip

    import anyenv

    with gzip.open(ICON_FILE, "r") as file:
        return anyenv.load_json(file.read())


if __name__ == "__main__":
    # idx = load_icon_index()
    # print(idx)
    write_icon_index()
