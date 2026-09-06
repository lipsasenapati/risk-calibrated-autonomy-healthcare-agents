"""In-memory tools; side effects are recorded in logs, never sent to real systems."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from .scenarios import Episode, snapshot_for


TOOL_SCHEMAS = [
    {"type": "function", "name": "get_patient_snapshot", "description": "Read the synthetic care-coordination snapshot.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "schedule_specialist", "description": "Schedule a synthetic specialist review.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "send_patient_message", "description": "Send a synthetic, non-clinical coordination message.", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "escalate_to_human", "description": "Escalate the episode to a human coordinator.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"], "additionalProperties": False}, "strict": True},
]


@dataclass
class ToolEnvironment:
    episode: Episode
    audit: list[dict[str, Any]] = field(default_factory=list)
    completed: bool = False

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "get_patient_snapshot": lambda _: snapshot_for(self.episode),
            "schedule_specialist": self._schedule,
            "send_patient_message": self._message,
            "escalate_to_human": self._escalate,
        }
        if name not in handlers:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        outcome = handlers[name](arguments)
        self.audit.append({"tool": name, "arguments": arguments, "outcome": outcome})
        return outcome

    def _schedule(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.completed = True
        return {"ok": True, "event": "synthetic specialist review scheduled", "reason": arguments["reason"]}

    def _message(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "event": "synthetic patient message recorded", "message": arguments["message"]}

    def _escalate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.completed = True
        return {"ok": True, "event": "human coordinator notified", "reason": arguments["reason"]}

    @staticmethod
    def json(result: dict[str, Any]) -> str:
        return json.dumps(result, sort_keys=True)
