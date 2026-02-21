"""
Command Registry — SSoT for all Typer CLI commands.

Moved from src/cli/registry.py. The old path re-exports this for backward compat.
"""
from dataclasses import dataclass, field
from typing import Callable, List, Dict


@dataclass
class CommandMetadata:
    name: str
    description: str
    example: str
    func: Callable
    kwargs: Dict = field(default_factory=dict)


class CommandRegistry:
    """
    Singleton registry that stores all CLI command metadata.

    Usage (in a command module)::

        from src.registry import command_registry

        @command_registry.register(name="ls", description="...", example="ct ls")
        def ls(...): ...

    Usage (in main.py)::

        for cmd in command_registry.commands:
            app.command(name=cmd.name, **cmd.kwargs)(cmd.func)
    """

    _instance = None
    commands: List[CommandMetadata] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, name: str, description: str, example: str, **kwargs):
        """Decorator that registers a function as a CLI command."""
        def decorator(func: Callable):
            self.commands.append(CommandMetadata(
                name=name,
                description=description,
                example=example,
                func=func,
                kwargs=kwargs,
            ))
            return func
        return decorator


command_registry = CommandRegistry()
