from __future__ import annotations

from typing import Dict


def ensure_required(entities: Dict, required: Dict[str, str]) -> None:
    """Validate required fields are present; raise ValueError if missing.

    required: dict of field->human_label
    """
    missing = [label for field, label in required.items() if not entities.get(field)]
    if missing:
        raise ValueError("Missing required field(s): " + ", ".join(missing))
