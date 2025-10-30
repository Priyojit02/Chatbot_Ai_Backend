import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local services
from services.sap_service import get_telephone_address, create_update_telephone_address
from services.nlp_service import extract_telephone_details
from services.sap_postal_service import get_postal_address, create_update_postal_address
from services.nlp_postal_service import extract_postal_details
from langchain_openai import ChatOpenAI

# -----------------------------------------------------------------------------
# App & Logging
# -----------------------------------------------------------------------------
app = FastAPI(title="SAP Plant Address + General Chatbot", version="1.1")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("main_app")

# Configure from centralized settings (if available)
try:
    from config import get_settings, configure_logging, build_cors

    settings = get_settings()
    configure_logging(settings)
    app = build_cors(settings)(app)
    # Optional middlewares
    try:
        from middleware.request_id import RequestIDMiddleware
        from middleware.timing import TimingMiddleware

        app.add_middleware(RequestIDMiddleware)
        app.add_middleware(TimingMiddleware, slow_ms=getattr(settings.logging, "slow_request_threshold_ms", 1200))
    except Exception:
        logging.getLogger("main_app").warning("custom middlewares not added")
except Exception:
    logging.getLogger("main_app").warning("config.py not fully applied (import or setup issue)")

# Include v2 and v3 routers (namespaced) without breaking existing endpoint
try:
    from app_route import router as v2_router

    # We add router under its own /v2 prefix, so the old endpoint stays intact
    app.include_router(v2_router)
except Exception:
    # Non-fatal if v2 components are missing; log and continue with v1
    logging.getLogger("main_app").warning("v2 router not included (import failed)")

try:
    from dynamic_router import router as v3_router
    app.include_router(v3_router)
except Exception:
    logging.getLogger("main_app").warning("v3 router not included (import failed)")

# -----------------------------------------------------------------------------
# Request Model
# -----------------------------------------------------------------------------
class UserQuery(BaseModel):
    user_query: str

# -----------------------------------------------------------------------------
# LLM for general replies
# -----------------------------------------------------------------------------
llm = ChatOpenAI(
    model="bedrock.anthropic.claude-opus-4",
    temperature=0,
    base_url="https://genai-sharedservice-americas.pwcinternal.com",
    api_key=os.getenv("OPENAI_API_KEY")
)

# -----------------------------------------------------------------------------
# Helper: validate required fields
# -----------------------------------------------------------------------------
def ensure_required_fields(entities: dict, required: list):
    missing = [f for f in required if not entities.get(f)]
    if missing:
        # Instead of hard 400, return a structured response so frontend can clarify
        raise HTTPException(
            status_code=400,
            detail=f"Missing required field(s): {', '.join(missing)}"
        )

# -----------------------------------------------------------------------------
# Endpoint
# -----------------------------------------------------------------------------
@app.post("/process-user-query/")
async def process_user_query(request: UserQuery):
    try:
        # Step 1: Run both NLP extractors
        tel_data = extract_telephone_details(request.user_query)
        post_data = extract_postal_details(request.user_query)

        # Prefer whichever extractor didn’t return GeneralChat
        if tel_data["intent"] != "GeneralChat":
            extracted_data = tel_data
        elif post_data["intent"] != "GeneralChat":
            extracted_data = post_data
        else:
            extracted_data = {"intent": "GeneralChat", "entities": {}}

        intent = extracted_data.get("intent")
        entities = extracted_data.get("entities", {})
        logger.info(f"Intent: {intent} | Entities: {entities}")

        # Step 2: Route based on intent
        if intent == "GetTelephoneAddress":
            result = get_telephone_address()
            return {"status": "success", "type": "sap", "data": result}

        elif intent in ("CreateTelephoneAddress", "UpdateTelephoneAddress"):
            ensure_required_fields(entities, ["PLANT"])
            result = create_update_telephone_address(entities)
            return {"status": "success", "type": "sap", "data": result}

        elif intent == "GetPostalAddress":
            result = get_postal_address()
            return {"status": "success", "type": "sap", "data": result}

        elif intent in ("CreatePostalAddress", "UpdatePostalAddress"):
            ensure_required_fields(entities, ["PLANT"])
            result = create_update_postal_address(entities)
            return {"status": "success", "type": "sap", "data": result}

        elif intent == "GeneralChat":
            response = llm.invoke(request.user_query)
            return {"status": "success", "type": "general", "reply": response.content}

        else:
            logger.warning(f"Unknown intent: {intent}, defaulting to general chat")
            response = llm.invoke(request.user_query)
            return {"status": "success", "type": "general", "reply": response.content}

    except HTTPException:
        # Already structured, just bubble up
        raise
    except ValueError as ve:
        logger.error(f"NLP/Validation error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error processing user query")
        raise HTTPException(status_code=500, detail="Internal Server Error")
