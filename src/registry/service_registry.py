"""
Service Registry — SSoT for all application services.

Moved from src/services/service_registry.py. The old path re-exports this for backward compat.
"""
import yaml
from pathlib import Path
from typing import Callable, Dict, Any, Optional


class ServiceRegistry:
    """
    Singleton registry that maps service names to their init/health callables,
    driven by config/settings.yaml.

    Usage (in a service module)::

        from src.registry import service_registry

        service_registry.register("bedrock", init_func=_init, health_func=_health)

    Usage (in init.py / health.py)::

        for name, svc in service_registry.get_active_services().items():
            svc["init"]()
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._services: Dict[str, Dict[str, Any]] = {}
            cls._instance._active_services = cls._instance._load_active_services()
        return cls._instance

    def _load_active_services(self) -> Dict[str, bool]:
        settings_path = Path("config/settings.yaml")
        if not settings_path.exists():
            return {}
        try:
            with open(settings_path, "r") as f:
                settings = yaml.safe_load(f) or {}
                return settings.get("services", {})
        except Exception:
            return {}

    def register(
        self,
        name: str,
        init_func: Optional[Callable] = None,
        health_func: Optional[Callable] = None,
    ):
        """Register a service with its initialization and health-check functions."""
        is_active = self._active_services.get(name, True)
        self._services[name] = {
            "init": init_func,
            "health": health_func,
            "active": is_active,
        }

    def get_active_services(self) -> Dict[str, Dict[str, Any]]:
        return {name: data for name, data in self._services.items() if data["active"]}

    def get_all_services(self) -> Dict[str, Dict[str, Any]]:
        return self._services


service_registry = ServiceRegistry()
