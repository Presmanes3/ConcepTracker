"""
Backward-compat shim — real implementation lives in src/registry/command_registry.py.
All new code should import from src.registry instead.
"""
from src.registry.command_registry import CommandRegistry, CommandMetadata, command_registry  # noqa: F401

# Legacy alias used by all existing command modules and main.py
registry = command_registry
