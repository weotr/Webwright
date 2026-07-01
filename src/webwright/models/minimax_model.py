"""MiniMax-M3 chat completions model backend.

MiniMax-M3 is MiniMax's flagship multimodal model, compatible with OpenAI
Chat Completions API. It supports text and image input natively.
"""

from __future__ import annotations

from typing import Any

from webwright.models.base import BaseModel, BaseModelConfig, OptStr
from webwright.models.openrouter_model import (
    _extract_chat_completions_text,
    _metrics_input_from_chat_messages,
    _serialize_chat_messages,
    _usage_metrics_from_chat_completions,
)

__all__ = [
    "MiniMaxModel",
    "MiniMaxModelConfig",
]


class MiniMaxModelConfig(BaseModelConfig):
    model_name: OptStr = "MiniMax-M3"
    minimax_api_key: OptStr = ""
    minimax_endpoint: OptStr = "https://api.minimaxi.com/v1/chat/completions"


class MiniMaxModel(BaseModel):
    _API_KEY_FIELD = "minimax_api_key"
    _ENV_VAR = "MINIMAX_API_KEY"
    _LOG_SOURCE = "minimax"
    _MAX_RATE_LIMIT_RETRIES = 5
    _MAX_TRANSIENT_RETRIES = 5
    _DEFAULT_CONFIG_CLASS = MiniMaxModelConfig

    def _request_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.minimax_api_key}",
        }

    def _post_url(self) -> str:
        return self.config.minimax_endpoint

    def _build_payload(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": _serialize_chat_messages(messages),
            "stream": False,
            "max_completion_tokens": self.config.max_output_tokens,
            "thinking": {"type": "disabled"},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "playwright_step",
                    "strict": True,
                    "schema": self._response_schema(),
                },
            },
        }
        return payload

    def _build_text_payload(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": _serialize_chat_messages(messages),
            "stream": False,
            "max_completion_tokens": self.config.max_output_tokens,
            "thinking": {"type": "disabled"},
        }
        return payload

    def _request_metrics_input(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return _metrics_input_from_chat_messages(payload.get("messages") or [])

    def _extract_text(self, payload: dict[str, Any]) -> str:
        return _extract_chat_completions_text(payload)

    def _usage_metrics_from_payload(self, payload: dict[str, Any]) -> dict[str, int]:
        return _usage_metrics_from_chat_completions(payload)
