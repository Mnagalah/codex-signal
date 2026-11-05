"""Version-scoped payload loading for the existing, persistent MCP host."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

PREFIX = "codex_menu_payload_"
_current: tuple[pathlib.Path, type] | None = None
_serial = 0


def prune_payload_modules(keep: str) -> None:
    """Drop import-table references, not live objects owned by finishing readers.

    Also bounds namespaces when an older installed host calls its original
    timestamp-based loader. Existing callbacks keep their own globals alive
    until they finish; they are never reloaded in place.
    """
    if not keep.startswith(PREFIX):
        return
    for name in tuple(sys.modules):
        if name.startswith(PREFIX) and name != keep and not name.startswith(keep + "."):
            del sys.modules[name]


def load_plugin_class(root: pathlib.Path):
    global _current, _serial
    root = root.resolve()
    if _current is not None and _current[0] == root:
        return _current[1]  # Installed version directories are immutable.
    _serial += 1
    name = PREFIX + str(id(load_plugin_class)) + "_" + str(_serial)
    package = types.ModuleType(name)
    package.__path__ = [str(root / "server")]
    sys.modules[name] = package
    try:
        spec = importlib.util.spec_from_file_location(name + ".main", root / "server/main.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        cls = module.Plugin
    except BaseException:
        for key in tuple(sys.modules):
            if key == name or key.startswith(name + "."):
                del sys.modules[key]
        raise
    _current = root, cls  # Retain only the current factory, not every release.
    prune_payload_modules(name)
    return cls
