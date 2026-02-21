"""
Central registry package — Single Source of Truth for all singletons.

Usage:
    from src.registry import command_registry, service_registry, repos, agents
"""
from src.registry.command_registry import CommandRegistry, CommandMetadata, command_registry
from src.registry.service_registry import ServiceRegistry, service_registry
from src.registry.repository_registry import RepositoryRegistry, repos
from src.registry.agent_registry import AgentRegistry, agent_registry

__all__ = [
    "CommandRegistry", "CommandMetadata", "command_registry",
    "ServiceRegistry", "service_registry",
    "RepositoryRegistry", "repos",
    "AgentRegistry", "agent_registry",
]
