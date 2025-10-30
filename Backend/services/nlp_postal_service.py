import os
import json
import logging
from dotenv import load_dotenv

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nlp_postal")

llm = ChatOpenAI(
    model="bedrock.anthropic.claude-opus-4",
    temperature=0,
    base_url="https://genai-sharedservice-americas.pwcinternal.com",
    api_key=os.getenv("OPENAI_API_KEY"),
)

# -----------------------------------------------------------------------------
# Prompt Template
# -----------------------------------------------------------------------------
prompt_template_postal = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an intent and entity extractor for SAP plant postal address operations. "
        "If the query is not related to SAP postal addresses, classify it as GeneralChat."
    ),
    (
        "user",
        """
Extract the following entities from the user query. If the user does not provide a value, leave it as an empty string.

Entities to extract:
- PLANT
- ADDR_VERS
- FROM_DATE
- TO_DATE
- TITLE
- NAME
- NAME_2
- NAME_3
- NAME_4
- CONV_NAME
- C_O_NAME
- CITY
- DISTRICT
- CITY_NO
- DISTRCT_NO
- POSTL_COD1
- POSTL_COD2
- POSTL_COD3
- STREET
- STREET_NO
- STR_ABBR
- HOUSE_NO
- HOUSE_NO2
- HOUSE_NO3
- STR_SUPPL1
- STR_SUPPL2
- STR_SUPPL3
- LOCATION
- BUILDING
- FLOOR
- ROOM_NO
- COUNTRY
- COUNTRYISO
- LANGU
- LANGU_ISO
- REGION
- SORT1
- SORT2

Classify the intent into one of:
- GetPostalAddress
- CreatePostalAddress
- UpdatePostalAddress
- GeneralChat

Return EXACTLY this JSON shape (no commentary, no code fences):
{
  "intent": "",
  "entities": {
    "PLANT": "",
    "ADDR_VERS": "",
    "FROM_DATE": "",
    "TO_DATE": "",
    "TITLE": "",
    "NAME": "",
    "NAME_2": "",
    "NAME_3": "",
    "NAME_4": "",
    "CONV_NAME": "",
    "C_O_NAME": "",
    "CITY": "",
    "DISTRICT": "",
    "CITY_NO": "",
    "DISTRCT_NO": "",
    "POSTL_COD1": "",
    "POSTL_COD2": "",
    "POSTL_COD3": "",
    "STREET": "",
    "STREET_NO": "",
    "STR_ABBR": "",
    "HOUSE_NO": "",
    "HOUSE_NO2": "",
    "HOUSE_NO3": "",
    "STR_SUPPL1": "",
    "STR_SUPPL2": "",
    "STR_SUPPL3": "",
    "LOCATION": "",
    "BUILDING": "",
    "FLOOR": "",
    "ROOM_NO": "",
    "COUNTRY": "",
    "COUNTRYISO": "",
    "LANGU": "",
    "LANGU_ISO": "",
    "REGION": "",
    "SORT1": "",
    "SORT2": ""
  }
}

Query: "{description}"
"""
    ),
])

output_parser = StrOutputParser()

# -----------------------------------------------------------------------------
# Extractor Function
# -----------------------------------------------------------------------------
def extract_postal_details(description: str) -> dict:
    """Extract intent and all SAP Postal Address entities or fallback to GeneralChat."""
    chain = prompt_template_postal | llm | output_parser
    response = chain.invoke({"description": description}).strip()

    # Clean any stray code fences if present
    if "```" in response:
        parts = [p for p in response.split("```") if "{" in p and "}" in p]
        if parts:
            response = max(parts, key=len).strip()

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from LLM: {response}")
        raise ValueError(f"Invalid JSON from LLM: {response}")

    intent = parsed.get("intent", "")
    if intent not in ("GetPostalAddress", "CreatePostalAddress", "UpdatePostalAddress", "GeneralChat"):
        logger.warning(f"Unknown intent returned: {intent}. Defaulting to GeneralChat.")
        intent = "GeneralChat"

    return {"intent": intent, "entities": parsed.get("entities", {})}
