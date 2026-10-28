"""LLM factory and privacy-aware hybrid provider router."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from logger import logger

load_dotenv()

_model: HybridChatModel | None = None


@dataclass(frozen=True)
class RoutingDecision:
    """The provider selected for one model request."""

    provider: str
    sensitive: bool
    reason: str


class HybridChatModel:
    """LangChain-compatible facade selecting Ollama or Groq per invocation."""

    _SENSITIVE_PATTERNS = (
        re.compile(r"\b(personal|private|confidential|proprietary|secret|internal)\b", re.I),
        re.compile(r"\b(academic assignment|homework|thesis|student|resume|cv)\b", re.I),
        re.compile(r"\b(read|open|inspect|summari[sz]e|analy[sz]e|edit|write|modify)\b.{0,80}\b(file|folder|directory|document|pdf|docx|csv|json|code|repository|repo)\b", re.I),
        re.compile(r"(?:[A-Za-z]:[\\/]|(?:\\\\|//)|\b(?:src|server|frontend|docs|tmp)[\\/])", re.I),
        re.compile(r"\b(?:\.env|id_rsa|credentials|secrets?\.(?:json|ya?ml)|password|api[_ -]?key|token)\b", re.I),
        re.compile(r"\b(?:medical|health|financial|bank|credit card|ssn|social security|email inbox)\b", re.I),
    )

    def __init__(self, cloud: Any | None, local: Any, mode: str = "hybrid") -> None:
        self.cloud = cloud
        self.local = local
        self.mode = mode.lower().strip()

    @classmethod
    def is_sensitive(cls, value: Any) -> bool:
        text = _input_text(value)
        return any(pattern.search(text) for pattern in cls._SENSITIVE_PATTERNS)

    def decide(self, value: Any) -> RoutingDecision:
        sensitive = self.is_sensitive(value)
        if self.mode == "local" or sensitive:
            return RoutingDecision("ollama", sensitive, "privacy-sensitive input" if sensitive else "local mode")
        if self.cloud is not None and self.mode == "cloud":
            return RoutingDecision("groq", False, "cloud mode")
        if self.cloud is not None:
            return RoutingDecision("groq", False, "non-sensitive orchestration input")
        return RoutingDecision("ollama", False, "Groq is not configured")

    def _provider(self, value: Any) -> tuple[Any, RoutingDecision]:
        decision = self.decide(value)
        return (self.cloud if decision.provider == "groq" else self.local), decision

    def invoke(self, input: Any, config: dict | None = None, **kwargs: Any) -> Any:
        provider, decision = self._provider(input)
        logger.debug("LLM route selected | provider=%s | reason=%s", decision.provider, decision.reason)
        try:
            return provider.invoke(input, config=config, **kwargs)
        except Exception:
            if decision.provider == "groq":
                logger.warning("Groq invocation failed; retrying with Ollama")
                return self.local.invoke(input, config=config, **kwargs)
            raise

    async def ainvoke(self, input: Any, config: dict | None = None, **kwargs: Any) -> Any:
        provider, decision = self._provider(input)
        logger.debug("LLM route selected | provider=%s | reason=%s", decision.provider, decision.reason)
        try:
            return await provider.ainvoke(input, config=config, **kwargs)
        except Exception:
            if decision.provider == "groq":
                logger.warning("Groq invocation failed; retrying with Ollama")
                return await self.local.ainvoke(input, config=config, **kwargs)
            raise

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> RunnableLambda:
        """Bind tools while retaining per-call provider selection."""
        def invoke_bound(value: Any, config: dict | None = None) -> Any:
            provider, decision = self._provider(value)
            try:
                return provider.bind_tools(tools, **kwargs).invoke(value, config=config)
            except Exception:
                if decision.provider == "groq":
                    logger.warning("Groq tool invocation failed; retrying with Ollama")
                    return self.local.bind_tools(tools, **kwargs).invoke(value, config=config)
                raise

        async def ainvoke_bound(value: Any, config: dict | None = None) -> Any:
            provider, decision = self._provider(value)
            try:
                return await provider.bind_tools(tools, **kwargs).ainvoke(value, config=config)
            except Exception:
                if decision.provider == "groq":
                    logger.warning("Groq tool invocation failed; retrying with Ollama")
                    return await self.local.bind_tools(tools, **kwargs).ainvoke(value, config=config)
                raise

        return RunnableLambda(invoke_bound, afunc=ainvoke_bound)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> RunnableLambda:
        """Apply structured output after selecting the provider for the input."""
        def invoke_structured(value: Any, config: dict | None = None) -> Any:
            provider, decision = self._provider(value)
            try:
                return provider.with_structured_output(schema, **kwargs).invoke(value, config=config)
            except Exception:
                if decision.provider == "groq":
                    logger.warning("Groq structured invocation failed; retrying with Ollama")
                    return self.local.with_structured_output(schema, **kwargs).invoke(value, config=config)
                raise

        async def ainvoke_structured(value: Any, config: dict | None = None) -> Any:
            provider, decision = self._provider(value)
            try:
                return await provider.with_structured_output(schema, **kwargs).ainvoke(value, config=config)
            except Exception:
                if decision.provider == "groq":
                    logger.warning("Groq structured invocation failed; retrying with Ollama")
                    return await self.local.with_structured_output(schema, **kwargs).ainvoke(value, config=config)
                raise

        return RunnableLambda(invoke_structured, afunc=ainvoke_structured)


def _input_text(value: Any) -> str:
    """Extract text for classification without serializing provider objects."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_input_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_input_text(item) for item in value)
    content = getattr(value, "content", None)
    if content is not None:
        return _input_text(content)
    return str(value)


def get_model() -> HybridChatModel:
    """Return the shared hybrid model.

    ``LLM_ROUTING_MODE`` is ``hybrid`` by default and may be ``local`` or
    ``cloud``. ``GROQ_MODEL`` defaults to ``openai/gpt-oss-120b``;
    ``OLLAMA_MODEL`` defaults to ``llama3.2``.
    """
    global _model
    if _model is not None:
        return _model

    mode = os.getenv("LLM_ROUTING_MODE", "hybrid").lower().strip()
    local_model = os.getenv("OLLAMA_MODEL", "llama3.2")
    ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    ollama_num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))
    local = ChatOllama(
        model=local_model,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.2,
        num_predict=ollama_num_predict,
        keep_alive="10m",
        async_client_kwargs={"timeout": ollama_timeout},
        sync_client_kwargs={"timeout": ollama_timeout},
    )

    api_key = os.getenv("GROQ_API_KEY")
    cloud = None
    if api_key and mode != "local":
        cloud_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        cloud = ChatGroq(model=cloud_model, temperature=0.2)
        logger.info("Groq configured for non-sensitive requests | model=%s", cloud_model)
    else:
        logger.info("Groq unavailable; using Ollama for all requests")

    _model = HybridChatModel(cloud=cloud, local=local, mode=mode)
    logger.info(
        "Ollama configured | model=%s | routing_mode=%s | timeout=%ss | max_output=%s",
        local_model,
        mode,
        ollama_timeout,
        ollama_num_predict,
    )
    return _model
