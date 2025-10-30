from __future__ import annotations

from typing import Dict

from .base import ensure_required
from services.sap_service import get_telephone_address, create_update_telephone_address


def handle(intent: str, entities: Dict, context: Dict) -> Dict:
    if intent == "GetTelephoneAddress":
        result = get_telephone_address()
        return {"status": "success", "type": "sap", "data": result}

    if intent in ("CreateTelephoneAddress", "UpdateTelephoneAddress"):
        ensure_required(entities, {"PLANT": "PLANT"})
        result = create_update_telephone_address(entities)
        return {"status": "success", "type": "sap", "data": result}

    raise ValueError(f"Unsupported intent for telephone handler: {intent}")
