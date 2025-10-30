from __future__ import annotations

from typing import Dict

from .base import ensure_required
from services.sap_postal_service import (
    get_telephone_address as get_postal_address,  # replace with actual postal when implemented
    create_update_telephone_address as create_update_postal_address,
)


def handle(intent: str, entities: Dict, context: Dict) -> Dict:
    if intent == "GetPostalAddress":
        result = get_postal_address()
        return {"status": "success", "type": "sap", "data": result}

    if intent in ("CreatePostalAddress", "UpdatePostalAddress"):
        ensure_required(entities, {"PLANT": "PLANT"})
        result = create_update_postal_address(entities)
        return {"status": "success", "type": "sap", "data": result}

    raise ValueError(f"Unsupported intent for postal handler: {intent}")
