from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class GovernanceEvent(BaseModel):
    agent_id: str
    action_type: str
    timestamp: datetime
    input_hash: str
    input_type: str
    output_summary: str
    rules_applied: list[str]
    rules_triggered: list[str]
    confidence: Optional[float] = None
    human_in_loop: str
    user_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    metadata: dict = {}


def hash_input_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_input_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_input_dict(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
