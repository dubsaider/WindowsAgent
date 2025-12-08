import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging


@dataclass
class AgentState:
    """Хранит хеш последней отправленной конфигурации и время отправки."""

    last_hash: Optional[str] = None
    last_sent_ts: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"last_hash": self.last_hash, "last_sent_ts": self.last_sent_ts}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AgentState":
        return AgentState(
            last_hash=data.get("last_hash"),
            last_sent_ts=data.get("last_sent_ts"),
        )


class StateStore:
    """Простое файловое хранилище состояния агента."""

    def __init__(self, path: str, logger: logging.Logger):
        self.path = path
        self.logger = logger

    def load(self) -> AgentState:
        if not os.path.exists(self.path):
            return AgentState()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return AgentState.from_dict(data)
        except Exception as e:
            self.logger.warning(f"Не удалось прочитать состояние: {e}")
            return AgentState()

    def save(self, state: AgentState):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"Не удалось сохранить состояние: {e}")

