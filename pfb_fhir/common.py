"""Useful functions."""
from typing import Any

LOGGED_ALREADY = set({})


def first_occurrence(message: str) -> bool:
    """Return True if we haven't logged message already."""
    if message in LOGGED_ALREADY:
        return False
    LOGGED_ALREADY.add(message)
    return True


def is_primitive(obj: Any) -> bool:
    """Is the argument a primitive?, not a collection or object."""
    return not isinstance(obj, (dict, list, tuple)) and not hasattr(obj, '__dict__')
