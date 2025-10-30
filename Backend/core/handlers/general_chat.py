from __future__ import annotations

import os
from typing import Dict

from langchain_openai import ChatOpenAI


def handle(intent: str, entities: Dict, context: Dict) -> Dict:
    settings = context["settings"]
    llm = ChatOpenAI(
        model=settings.llm.default_model,
        temperature=settings.llm.temperature,
        base_url=settings.llm.base_url,
        api_key=os.getenv(settings.llm.api_key_env),
    )
    question = context.get("user_query") or entities.get("question") or "Hello"
    response = llm.invoke(question)
    return {"status": "success", "type": "general", "reply": response.content}
