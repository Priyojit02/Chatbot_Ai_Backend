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
logger = logging.getLogger("nlp_telephone")

llm = ChatOpenAI(
    model="bedrock.anthropic.claude-opus-4",
    temperature=0,
    base_url="https://genai-sharedservice-americas.pwcinternal.com",
    api_key=os.getenv("OPENAI_API_KEY"),
)

# -----------------------------------------------------------------------------
# Prompt Template
# -----------------------------------------------------------------------------
prompt_template = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an intent and entity extractor for SAP plant telephone address operations. "
        "If the query is not related to SAP telephone addresses, classify it as GeneralChat."
    ),
    (
        "user",
        """
Extract the following entities from the user query. If the user does not provide a value, leave it as an empty string.

Entities to extract:
- PLANT
- COUNTRY
- COUNTRYISO
- STD_NO
- TELEPHONE
- EXTENSION
- TEL_NO
- CALLER_NO
- STD_RECIP
- R_3_USER
- HOME_FLAG
- CONSNUMBER
- ERRORFLAG
- FLG_NOUSE
- VALID_FROM
- VALID_TO
- MSG_TYP
- MSG_DESC

Classify the intent into one of:
- GetTelephoneAddress
- CreateTelephoneAddress
- UpdateTelephoneAddress
- GeneralChat

Return EXACTLY this JSON shape (no commentary, no code fences):
{
  "intent": "",
  "entities": {
    "PLANT": "",
    "COUNTRY": "",
    "COUNTRYISO": "",
    "STD_NO": "",
    "TELEPHONE": "",
    "EXTENSION": "",
    "TEL_NO": "",
    "CALLER_NO": "",
    "STD_RECIP": "",
    "R_3_USER": "",
    "HOME_FLAG": "",
    "CONSNUMBER": "",
    "ERRORFLAG": "",
    "FLG_NOUSE": "",
    "VALID_FROM": "",
    "VALID_TO": "",
    "MSG_TYP": "",
    "MSG_DESC": ""
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
def extract_telephone_details(description: str) -> dict:
    """Extract intent and all SAP Telephone Address entities or fallback to GeneralChat."""
    chain = prompt_template | llm | output_parser
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
    if intent not in ("GetTelephoneAddress", "CreateTelephoneAddress", "UpdateTelephoneAddress", "GeneralChat"):
        logger.warning(f"Unknown intent returned: {intent}. Defaulting to GeneralChat.")
        intent = "GeneralChat"

    return {"intent": intent, "entities": parsed.get("entities", {})}
