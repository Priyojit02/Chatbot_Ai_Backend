"""
Intent registry and dispatcher for dynamic, config-driven routing.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

from pydantic import BaseModel


class DispatchResult(BaseModel):
    status: str
    type: str
    data: Optional[dict] = None
    reply: Optional[str] = None


HandlerFunc = Callable[[str, dict, dict], dict]


class IntentRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, HandlerFunc] = {}

    def register(self, intent: str, handler: HandlerFunc) -> None:
        self._handlers[intent] = handler

    def has(self, intent: str) -> bool:
        return intent in self._handlers

    def dispatch(self, intent: str, entities: dict, context: dict) -> dict:
        if intent not in self._handlers:
            raise ValueError(f"No handler registered for intent '{intent}'")
        return self._handlers[intent](intent, entities or {}, context)


registry = IntentRegistry()
