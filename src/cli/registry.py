from dataclasses import dataclass
from typing import Callable, List, Optional

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Dict

@dataclass
class CommandMetadata:
    name: str
    description: str
    example: str
    func: Callable
    kwargs: Dict = field(default_factory=dict)

class CommandRegistry:
    _instance = None
    commands: List[CommandMetadata] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CommandRegistry, cls).__new__(cls)
        return cls._instance

    def register(self, name: str, description: str, example: str, **kwargs):
        def decorator(func: Callable):
            self.commands.append(CommandMetadata(
                name=name,
                description=description,
                example=example,
                func=func,
                kwargs=kwargs
            ))
            return func
        return decorator

registry = CommandRegistry()
