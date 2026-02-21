"""
Agent Registry — SSoT for all agent classes.

Agents self-register via the @agent_registry.register decorator at import time.
Consumers retrieve agent classes lazily to avoid loading LLM deps until needed.

Usage (in an agent module)::

    from src.registry import agent_registry
    from src.agents.base_agent import BaseAgent

    @agent_registry.register("tag_recommender")
    class TagRecommenderAgent(BaseAgent): ...

Usage (in an interactor)::

    from src.registry import agent_registry

    TagRecommender = agent_registry.get("tag_recommender")
    result = TagRecommender().run({"content": note.content, "summary": note.summary})
"""
from __future__ import annotations
from typing import Dict, Type, Callable


class AgentRegistry:
    """
    Singleton registry mapping string keys to agent classes.
    Supports both decorator-based registration and direct registration.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: Dict[str, Type] = {}
        return cls._instance

    def register(self, name: str) -> Callable:
        """
        Class decorator that registers an agent under the given name::

            @agent_registry.register("tag_recommender")
            class TagRecommenderAgent(BaseAgent): ...
        """
        def decorator(cls_):
            self._agents[name] = cls_
            return cls_
        return decorator

    def register_class(self, name: str, cls_: Type) -> None:
        """Programmatic registration without decorator (useful for bulk bootstrapping)."""
        self._agents[name] = cls_

    def get(self, name: str) -> Type:
        """
        Return the registered agent class, loading it lazily if it hasn't been
        imported yet via ``ensure_loaded()``.
        """
        if name not in self._agents:
            # Trigger lazy import of the default agent modules
            self._load_defaults()
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' is not registered. Available: {list(self._agents)}")
        return self._agents[name]

    def _load_defaults(self) -> None:
        """Import all agent modules so their @register decorators fire."""
        import importlib
        _modules = [
            "src.agents.tag_recommender_agent",
            "src.agents.linker_agent",
            "src.agents.gatekeeper_agent",
            "src.agents.normalizer_agent",
            "src.agents.taxonomy_agent",
            "src.agents.geo_namer_agent",
            "src.agents.markdown_formatter_agent",
            "src.agents.speech_cleaner_agent",
            "src.agents.retrospective_linker_agent",
            "src.agents.bidirectional_linker_agent",
            "src.agents.chunk_embed_agent",
        ]
        for mod in _modules:
            try:
                importlib.import_module(mod)
            except ImportError:
                pass

    @property
    def all(self) -> Dict[str, Type]:
        return dict(self._agents)


agent_registry = AgentRegistry()
