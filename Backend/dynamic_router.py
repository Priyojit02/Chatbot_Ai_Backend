from __future__ import annotations

import importlib
import json
import logging
import os
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_settings
from core.intent_registry import registry
from services.nlp_service import extract_telephone_details
from services.nlp_postal_service import extract_postal_details

logger = logging.getLogger("dynamic_router")
router = APIRouter(prefix="/v3", tags=["router-v3"])  # most dynamic router
settings = get_settings()


# Load intent config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "intents.json")
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        INTENT_CFG: Dict = json.load(f)
except Exception as e:
    INTENT_CFG = {"intents": {}}
    logger.warning(f"Failed to load intents config: {e}")


# Auto-register handlers from config
for intent, meta in INTENT_CFG.get("intents", {}).items():
    handler_mod = meta.get("handler")
    if not handler_mod:
        continue
    try:
        mod = importlib.import_module(f"core.handlers.{handler_mod}")
        registry.register(intent, getattr(mod, "handle"))
    except Exception as e:
        logger.warning(f"Failed to register handler for {intent}: {e}")


class DynamicPayload(BaseModel):
    user_query: Optional[str] = None
    intent: Optional[str] = None
    entities: Dict = {}


@router.post("/route")
async def route_dynamic(payload: DynamicPayload):
    try:
        # Determine intent/entities
        if payload.user_query:
            tel_data = extract_telephone_details(payload.user_query)
            post_data = extract_postal_details(payload.user_query)
            if tel_data.get("intent") != "GeneralChat":
                intent = tel_data["intent"]
                entities = tel_data.get("entities", {}) or {}
            elif post_data.get("intent") != "GeneralChat":
                intent = post_data["intent"]
                entities = post_data.get("entities", {}) or {}
            else:
                intent = "GeneralChat"
                entities = {}
        else:
            intent = payload.intent or "GeneralChat"
            entities = payload.entities or {}

        # Validate against config
        cfg = INTENT_CFG.get("intents", {}).get(intent)
        if not cfg or not registry.has(intent):
            # fallback to general chat if unknown
            intent = "GeneralChat"
            cfg = INTENT_CFG.get("intents", {}).get("GeneralChat", {})
        required = cfg.get("required", [])
        missing = [f for f in required if not entities.get(f)]
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing required field(s): {', '.join(missing)}")

        context = {"settings": settings, "user_query": payload.user_query}
        result = registry.dispatch(intent, entities, context)
        return result

    except HTTPException:
        raise
    except ValueError as ve:
        logger.error(f"Dynamic routing validation error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("Dynamic routing error")
        raise HTTPException(status_code=500, detail="Internal Server Error")
