from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage


class LLMProvider(ABC):
    """Abstract LLM provider."""

    @abstractmethod
    async def chat(self, messages: list[BaseMessage]) -> str:
        """Send messages and return the assistant response text."""
        ...

    async def chat_json(self, messages: list[BaseMessage]) -> list | dict:
        """Send messages and parse JSON response."""
        response = await self.chat(messages)
        # Extract JSON from markdown code blocks if present
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        return json.loads(response.strip())


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible LLM provider.

    Works with any OpenAI-compatible endpoint (DeepSeek, MiMo, local vLLM, ...)
    by setting ``LLM_BASE_URL``.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        from openai import AsyncOpenAI

        self.model = (
            model or os.environ.get("LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o"
        )
        self.base_url = base_url or os.environ.get("LLM_BASE_URL") or None
        thinking = os.environ.get("LLM_THINKING", "").strip().lower()
        self.extra_body = {"thinking": {"type": "disabled"}} if thinking == "disabled" else None
        # Without an explicit timeout a stalled provider request hangs the whole
        # review run (each segment calls the model); fail fast and let the node
        # degrade instead.
        self.client = AsyncOpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=self.base_url,
            timeout=float(os.environ.get("LLM_TIMEOUT_S", "90")),
            max_retries=int(os.environ.get("LLM_MAX_RETRIES", "1")),
        )

    async def chat(self, messages: list[BaseMessage]) -> str:
        formatted: list[dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                formatted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                formatted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted.append({"role": "assistant", "content": msg.content})

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": cast(Any, formatted),
            "temperature": 0.1,
        }
        if self.extra_body is not None:
            kwargs["extra_body"] = self.extra_body
        resp = await self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from anthropic import AsyncAnthropic

        self.model = model or os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")
        self.client = AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            timeout=float(os.environ.get("LLM_TIMEOUT_S", "90")),
            max_retries=int(os.environ.get("LLM_MAX_RETRIES", "1")),
        )

    async def chat(self, messages: list[BaseMessage]) -> str:
        system = ""
        formatted: list[dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system = str(msg.content)
            elif isinstance(msg, HumanMessage):
                formatted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted.append({"role": "assistant", "content": msg.content})

        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=cast(Any, formatted),
        )
        text_parts = [block.text for block in resp.content if hasattr(block, "text")]
        return "".join(text_parts)


class MockLLMProvider(LLMProvider):
    """Deterministic provider used by the offline demo and the test suite.

    Responses come from a JSON fixture::

        {
          "review":  {"<file path>": [ {...finding...} ], "*": [ ... ]},
          "fix":     "--- a/... +++ b/...",
          "self_evaluate": "confidence: 0.82 ...",
          "default": "..."
        }

    The prompt is classified by its system instructions, so the fixture does
    not depend on prompt wording beyond the three stable categories.
    """

    def __init__(self, fixture_path: str | None = None):
        self.fixture_path = (
            fixture_path or os.environ.get("MOCK_LLM_FIXTURE") or "fixtures/pr-101/mock_llm.json"
        )
        self._data: dict | None = None
        self.calls: list[str] = []

    def _load(self) -> dict:
        if self._data is None:
            with open(self.fixture_path, encoding="utf-8") as fh:
                self._data = json.load(fh)
        return self._data

    @staticmethod
    def _file_path_from_prompt(text: str) -> str | None:
        marker = "File: "
        idx = text.find(marker)
        if idx == -1:
            return None
        rest = text[idx + len(marker) :]
        return rest.split("\n", 1)[0].strip()

    async def chat(self, messages: list[BaseMessage]) -> str:
        joined = "\n".join(str(m.content) for m in messages)
        lowered = joined.lower()
        data = self._load()

        if "expert code reviewer" in lowered:
            reviews = data.get("review", {})
            path = self._file_path_from_prompt(joined) or ""
            findings = reviews.get(path, reviews.get("*", []))
            self.calls.append(f"review:{path}")
            return json.dumps(findings, ensure_ascii=False)
        if "unified diff patch" in lowered:
            self.calls.append("fix")
            return str(data.get("fix", ""))
        if "assess the fix quality" in lowered:
            self.calls.append("self_evaluate")
            return str(data.get("self_evaluate", "confidence: 0.7"))
        self.calls.append("default")
        return str(data.get("default", ""))


_PROVIDERS: dict[tuple[str, str, str, str, str], LLMProvider] = {}


def create_llm_provider(provider: str | None = None) -> LLMProvider:
    """Factory returning a cached provider per configuration.

    The review loop calls this once per code segment; creating a fresh SDK
    client каждый call leaks HTTP connections and file descriptors (one PR can
    have dozens of segments). Providers are stateless, so one per configuration
    is enough.
    """
    provider_name = (provider or os.environ.get("LLM_PROVIDER", "openai")).strip().lower()
    key = (
        provider_name,
        os.environ.get("LLM_MODEL", ""),
        os.environ.get("LLM_BASE_URL", ""),
        os.environ.get("LLM_THINKING", ""),
        os.environ.get("MOCK_LLM_FIXTURE", ""),
    )
    cached = _PROVIDERS.get(key)
    if cached is not None:
        return cached
    if provider_name == "anthropic":
        created: LLMProvider = AnthropicProvider()
    elif provider_name == "mock":
        created = MockLLMProvider()
    else:
        created = OpenAIProvider()
    _PROVIDERS[key] = created
    return created
