from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod

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
    """OpenAI-compatible LLM provider."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from openai import AsyncOpenAI

        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o")
        self.client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    async def chat(self, messages: list[BaseMessage]) -> str:
        formatted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                formatted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                formatted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted.append({"role": "assistant", "content": msg.content})

        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted,
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from anthropic import AsyncAnthropic

        self.model = model or os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")
        self.client = AsyncAnthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    async def chat(self, messages: list[BaseMessage]) -> str:
        system = ""
        formatted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system = msg.content
            elif isinstance(msg, HumanMessage):
                formatted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted.append({"role": "assistant", "content": msg.content})

        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=formatted,
        )
        return resp.content[0].text


def create_llm_provider(provider: str | None = None) -> LLMProvider:
    """Factory function to create the appropriate LLM provider."""
    provider_name = provider or os.environ.get("LLM_PROVIDER", "openai")
    if provider_name == "anthropic":
        return AnthropicProvider()
    return OpenAIProvider()
