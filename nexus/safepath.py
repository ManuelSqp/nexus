"""Paths built from outside data (request values, match ids, form fields) must stay where they belong.

`safe_join(base, *parts)` resolves the joined path and refuses anything that ends up outside `base` (`..`, absolute
parts, symlinks pointing out). Match ids are checked here too, so the web app, the CLI and the HenrikDev client
use the same rule.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

MATCH_ID_RE = re.compile(r"[A-Za-z0-9-]{1,64}")


class UnsafePath(ValueError):
    """A path that would leave its base folder."""


def valid_match_id(ref: str) -> bool:
    return isinstance(ref, str) and bool(MATCH_ID_RE.fullmatch(ref))


def safe_join(base: str | Path, *parts: str | int) -> Path:
    """base / parts, resolved; UnsafePath if the result isn't inside base."""
    root = os.path.realpath(base)
    p = os.path.realpath(os.path.join(root, *(str(x) for x in parts)))
    if p != root and not p.startswith(root.rstrip(os.sep) + os.sep):
        raise UnsafePath("path outside its folder")
    return Path(p)


def inside(base: str | Path, path: str | Path) -> bool:
    """Is path (resolved, ~ expanded) base itself or below it?"""
    root = Path(base).expanduser().resolve()
    p = Path(path).expanduser().resolve()
    return p == root or root in p.parents
