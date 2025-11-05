# streamlit_app.py — OData AI Chatbot (Streamlit + LangChain, single JSON file)
# ---------------------------------------------------------------------------------
# What this does
# • Reads ONE OData metadata JSON from disk (path configurable in sidebar)
# • Runs a natural, non‑technical chat using an LLM (LangChain + OpenAI) over that metadata
# • Bot figures out intent (create / update / read), which entity to use, and which fields to ask for
# • Uses entity + field DESCRIPTIONS when talking with the user
# • Confirms the final payload and (optionally) POSTs to your backend
# • Code is independent of the JSON contents; you can swap in another file with the same schema
#
# Quick start
#   pip install streamlit langchain langchain-core langchain-openai pydantic requests python-dotenv
#   export OPENAI_API_KEY=sk-...   # or set in .env
#   streamlit run streamlit_app.py
#
# JSON expectation (single file)
#   ./odata_metadata.json   (you can change the path in the app’s sidebar)
#   Shape matches the sample we built earlier: { service_name, entities:[ {entity_name, description, primary_key, fields:[{ name, description, type, key, ...}] } ] }

from __future__ import annotations
import json
import re
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from pydantic import BaseModel, Field

# LangChain LLM
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from dotenv import load_dotenv
load_dotenv()  # loads .env into environment

# ---------------------------------------------------------------------------------
# Data models for the metadata file
# ---------------------------------------------------------------------------------
@dataclass
class ODataField:
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    abap_type: Optional[str] = None
    key: Optional[bool] = False

@dataclass
class ODataEntity:
    entity_name: str
    description: Optional[str] = None
    primary_key: Optional[List[str]] = None
    fields: List[ODataField] = None  # type: ignore

@dataclass
class ODataServiceMeta:
    service_name: str
    service_version: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    entities: List[ODataEntity] = None  # type: ignore

# ---------------------------------------------------------------------------------
# App config
# ---------------------------------------------------------------------------------
DEFAULT_METADATA_PATH = "./odata_metadata.json"  # put your single JSON here
DEFAULT_BACKEND_URL = "http://localhost:8000/api/odata/post"  # FastAPI endpoint to receive POSTs

st.set_page_config(page_title="OData Chatbot (Streamlit + LangChain)", page_icon="🤖", layout="wide")

# ---------------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------------

def load_metadata(path: str) -> ODataServiceMeta:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # map to dataclasses
    entities: List[ODataEntity] = []
    for ent in raw.get("entities", []):
        fields = [ODataField(**fld) for fld in ent.get("fields", [])]
        entities.append(ODataEntity(
            entity_name=ent.get("entity_name"),
            description=ent.get("description"),
            primary_key=ent.get("primary_key"),
            fields=fields,
        ))
    return ODataServiceMeta(
        service_name=raw.get("service_name"),
        service_version=raw.get("service_version"),
        description=raw.get("description"),
        base_url=raw.get("base_url"),
        entities=entities,
    )


def summarize_metadata(meta: ODataServiceMeta, max_chars: int = 4000) -> str:
    """Create a concise, model-friendly text summary of the metadata.
    Keeps within token/char budget and includes descriptions for natural chat."""
    parts: List[str] = []
    parts.append(f"Service: {meta.service_name}\nDescription: {meta.description or ''}")
    for e in meta.entities:
        parts.append(f"\nEntity: {e.entity_name}\n- About: {e.description or ''}")
        keys = e.primary_key or [f.name for f in e.fields if f.key]
        if keys:
            parts.append(f"- Keys: {', '.join(keys)}")
        # list all fields with descriptions (kept compact)
        field_lines = []
        for f in e.fields:
            desc = f.description or f.abap_type or (f.type or "")
            field_lines.append(f"  • {f.name}: {desc}")
        parts.append("- Fields:\n" + "\n".join(field_lines))
    text = "\n".join(parts)
    return text[:max_chars]


# ---------------------------------------------------------------------------------
# LLM scaffolding
# ---------------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are a warm, helpful assistant that speaks naturally (non‑technical) and helps a user create or update records in an SAP-like system via OData services.
You have a description of the service, its entities, and their fields (with plain‑English descriptions). Use those descriptions in conversation.
Your goals:
1) Understand the user's intent: create, update, or read.
2) Identify which entity fits best.
3) Ask for any missing required fields using friendly language. Use the field descriptions to explain what each field means.
4) When everything is ready, summarize what will be submitted in simple terms and ask for a final yes/no confirmation.
5) Never expose internal JSON or schemas; keep the tone human and conversational.
6) Ask for at most 2 things per message. Keep replies concise.
""".strip()

# We ask the model to produce TWO things in one response:
#  (A) a natural chat reply for the user
#  (B) a small JSON control block we can parse to update the app state

ASSISTANT_PROMPT = """
Context about the service and entities:

{metadata_brief}

Conversation so far:
{history}

User said: "{user_input}"

You must produce:
1) A friendly reply that continues the conversation in natural language (speak like a human, not a system). Use field descriptions.
2) A JSON control block enclosed in <control>...</control> tags with EXACT keys:
   {{
     "intent": "create" | "update" | "read" | "unknown",
     "entity": "<entity_name or empty string>",
     "fields_collected": {{ "FieldName": "Value" }},
     "fields_needed": ["FieldName", "..."],
     "ready_to_confirm": true | false
   }}

Rules:
- Choose the entity that best matches the user's wording.
- fields_needed should list missing required keys FIRST, then any commonly used fields.
- If the user confirmed previously, set ready_to_confirm=true.
- Keep the reply short and friendly.
""".strip()


class ControlBlock(BaseModel):
    intent: str = Field(default="unknown")
    entity: str = Field(default="")
    fields_collected: Dict[str, Any] = Field(default_factory=dict)
    fields_needed: List[str] = Field(default_factory=list)
    ready_to_confirm: bool = False


def build_llm(model_name: str = "gpt-4o-mini", temperature: float = 0.2) -> ChatOpenAI:
    # Set OPENAI_API_KEY via env or .env
    return ChatOpenAI(model=model_name, temperature=temperature,
                        api_key=os.getenv("OPENAI_API_KEY") )


def run_llm(meta: ODataServiceMeta, history: List[Dict[str, str]], user_input: str, llm: ChatOpenAI) -> (str, ControlBlock):
    metadata_brief = summarize_metadata(meta)
    hist_text = "\n".join([f"{m['role']}: {m['content']}" for m in history])

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", ASSISTANT_PROMPT),
    ])

    chain = prompt | llm | StrOutputParser()
    raw = chain.invoke({
        "metadata_brief": metadata_brief,
        "history": hist_text,
        "user_input": user_input,
    })

    # Extract <control>...</control> JSON safely
    control = ControlBlock()
    reply_text = raw
    m = re.search(r"<control>([\s\S]*?)</control>", raw)
    if m:
        reply_text = raw.replace(m.group(0), "").strip()
        try:
            parsed = json.loads(m.group(1))
            control = ControlBlock(**parsed)
        except Exception:
            pass
    return reply_text.strip(), control


# ---------------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history: List[Dict[str, str]] = []
if "meta" not in st.session_state:
    st.session_state.meta: Optional[ODataServiceMeta] = None
if "entity" not in st.session_state:
    st.session_state.entity: Optional[ODataEntity] = None
if "collected" not in st.session_state:
    st.session_state.collected: Dict[str, Any] = {}
if "intent" not in st.session_state:
    st.session_state.intent: str = "unknown"

# ---------------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------------
with st.sidebar:
    st.header("Setup")
    meta_path = st.text_input("Path to OData metadata JSON", value=DEFAULT_METADATA_PATH)
    backend_url = st.text_input("Backend POST URL", value=DEFAULT_BACKEND_URL)
    model_name = st.selectbox("LLM model", ["gpt-4o-mini", "gpt-4o", "gpt-4o-mini-translate", "gpt-4.1-mini"], index=0)
    temperature = st.slider("Creativity", 0.0, 1.0, 0.2, 0.05)

    if st.button("Load JSON"):
        try:
            st.session_state.meta = load_metadata(meta_path)
            st.success(f"Loaded service: {st.session_state.meta.service_name}")
            # reset flow
            st.session_state.history = []
            st.session_state.entity = None
            st.session_state.collected = {}
            st.session_state.intent = "unknown"
        except Exception as e:
            st.error(f"Failed to load metadata: {e}")

# ---------------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------------
st.title("🤖 OData Chatbot")

if not st.session_state.meta:
    st.info("Provide the path to your single OData JSON in the sidebar and click **Load JSON**.")
else:
    meta = st.session_state.meta
    st.caption(f"Service loaded: **{meta.service_name}**")

    # render conversation
    for m in st.session_state.history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_text = st.chat_input("Say something like 'update SalesOrderHeaderSet SalesOrder=5000012345 Currency=INR'")
    if user_text:
        st.session_state.history.append({"role": "user", "content": user_text})
        llm = build_llm(model_name=model_name, temperature=temperature)
        reply, control = run_llm(meta, st.session_state.history, user_text, llm)

        # Update state from control block
        if control.intent != "unknown":
            st.session_state.intent = control.intent
        if control.entity:
            # find entity object from metadata
            ent = next((e for e in meta.entities if e.entity_name.lower() == control.entity.lower()), None)
            if ent:
                st.session_state.entity = ent
        # merge collected values but only for known fields in the chosen entity
        if st.session_state.entity and control.fields_collected:
            allowed = {f.name.lower() for f in st.session_state.entity.fields}
            for k, v in control.fields_collected.items():
                if k.lower() in allowed:
                    st.session_state.collected[k] = v

        # If model listed fields needed, show friendly hints using descriptions
        needed_lines: List[str] = []
        if st.session_state.entity and control.fields_needed:
            fmap = {f.name: (f.description or f.abap_type or f.type) for f in st.session_state.entity.fields}
            for fname in control.fields_needed:
                hint = fmap.get(fname)
                if hint:
                    needed_lines.append(f"• **{fname}** — {hint}")
                else:
                    needed_lines.append(f"• **{fname}**")
            if needed_lines:
                reply += "\n\n" + "Please share:\n" + "\n".join(needed_lines)

        # If everything is ready, show confirmation widget
        with st.chat_message("assistant"):
            st.markdown(reply)

            ready = control.ready_to_confirm and (st.session_state.entity is not None)
            # also ensure all key fields are present
            if st.session_state.entity:
                keys = st.session_state.entity.primary_key or [f.name for f in st.session_state.entity.fields if f.key]
                missing_keys = [k for k in keys if not str(st.session_state.collected.get(k, "")).strip()]
                if missing_keys:
                    ready = False
                    st.info("To proceed, I still need: " + ", ".join(missing_keys))

            if ready and st.session_state.entity:
                # Show a clean confirmation table with descriptions
                rows = []
                for f in st.session_state.entity.fields:
                    if f.name in st.session_state.collected and str(st.session_state.collected[f.name]).strip() != "":
                        rows.append({
                            "Field": f.name,
                            "Description": f.description or f.abap_type or f.type,
                            "Value": st.session_state.collected[f.name],
                        })
                st.markdown("\n**Review:**")
                st.dataframe(rows, use_container_width=True, hide_index=True)

                if st.button("✅ Yes, submit this"):
                    payload = {
                        "service_name": meta.service_name,
                        "entity_name": st.session_state.entity.entity_name,
                        "data": st.session_state.collected,
                    }
                    try:
                        resp = requests.post(DEFAULT_BACKEND_URL, json=payload, timeout=30)
                    except Exception as e:
                        resp = None
                        st.error(f"POST error: {e}")
                    if resp is not None and getattr(resp, "ok", False):
                        st.success("Posted successfully.")
                        st.session_state.history.append({"role": "assistant", "content": "Got it! I've submitted that. What would you like to do next?"})
                        # reset values but keep metadata
                        st.session_state.entity = None
                        st.session_state.collected = {}
                        st.session_state.intent = "unknown"
                    else:
                        code = getattr(resp, "status_code", "?")
                        body = getattr(resp, "text", "")[:400]
                        st.error(f"Backend error {code}: {body}")

    # live helper panel
    st.markdown("---")
    with st.expander("What fields can I provide? (from metadata)"):
        if st.session_state.entity:
            ent = st.session_state.entity
            st.markdown(f"**{ent.entity_name}** — {ent.description or ''}")
            rows = [{"Field": f.name, "Description": f.description or f.abap_type or f.type, "Key": bool(f.key)} for f in ent.fields]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.caption("Tell me what you want to do, e.g., 'Create a sales order header'.")
