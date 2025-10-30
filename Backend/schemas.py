from __future__ import annotations

from typing import Optional, Dict
from pydantic import BaseModel, model_validator


class DynamicRequest(BaseModel):
    user_query: Optional[str] = None
    intent: Optional[str] = None
    entities: Dict = {}

    @model_validator(mode="after")
    def _check_one_of(self):
        if not self.user_query and not self.intent:
            raise ValueError("Provide either 'user_query' or ('intent' + 'entities')")
        return self
