"""
Reusable FastAPI router exposing a v2 endpoint that uses centralized Settings
from config.py and existing services for SAP Telephone and Postal flows.
"""
from __future__ import annotations

import os
import logging
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_settings
from services.sap_service import get_telephone_address, create_update_telephone_address
from services.sap_postal_service import get_telephone_address as get_postal_address  # placeholder if postal differs
from services.sap_postal_service import create_update_telephone_address as create_update_postal_address
from services.nlp_service import extract_telephone_details
from services.nlp_postal_service import extract_postal_details

# LLM via langchain-openai
from langchain_openai import ChatOpenAI


settings = get_settings()
logger = logging.getLogger("app_route")

# Build LLM client from settings
_llm_api_key = os.getenv(settings.llm.api_key_env)
llm = ChatOpenAI(
    model=settings.llm.default_model,
    temperature=settings.llm.temperature,
    base_url=settings.llm.base_url,
    api_key=_llm_api_key,
)

router = APIRouter(prefix="/v2", tags=["router-v2"])  # namespaced to avoid clashing with existing routes


class UserQuery(BaseModel):
    user_query: str


@router.post("/process-user-query/")
async def process_user_query_v2(request: UserQuery):
    try:
        tel_data = extract_telephone_details(request.user_query)
        post_data = extract_postal_details(request.user_query)

        if tel_data.get("intent") != "GeneralChat":
            extracted_data = tel_data
        elif post_data.get("intent") != "GeneralChat":
            extracted_data = post_data
        else:
            extracted_data = {"intent": "GeneralChat", "entities": {}}

        intent = extracted_data.get("intent")
        entities: Dict = extracted_data.get("entities", {}) or {}
        logger.info(f"[v2] Intent: {intent} | Entities: {entities}")

        if intent == "GetTelephoneAddress":
            result = get_telephone_address()
            return {"status": "success", "type": "sap", "data": result}

        elif intent in ("CreateTelephoneAddress", "UpdateTelephoneAddress"):
            if not entities.get("PLANT"):
                raise HTTPException(status_code=400, detail="Missing required field: PLANT")
            result = create_update_telephone_address(entities)
            return {"status": "success", "type": "sap", "data": result}

        elif intent == "GetPostalAddress":
            result = get_postal_address()
            return {"status": "success", "type": "sap", "data": result}

        elif intent in ("CreatePostalAddress", "UpdatePostalAddress"):
            if not entities.get("PLANT"):
                raise HTTPException(status_code=400, detail="Missing required field: PLANT")
            result = create_update_postal_address(entities)
            return {"status": "success", "type": "sap", "data": result}

        elif intent == "GeneralChat":
            response = llm.invoke(request.user_query)
            return {"status": "success", "type": "general", "reply": response.content}

        # Fallback to general chat
        response = llm.invoke(request.user_query)
        return {"status": "success", "type": "general", "reply": response.content}

    except HTTPException:
        raise
    except ValueError as ve:
        logger.error(f"[v2] NLP/Validation error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("[v2] Error processing user query")
        raise HTTPException(status_code=500, detail="Internal Server Error")
