import yaml
from pathlib import Path
from typing import Callable, Dict, Any, Optional

class ServiceRegistry:
    def __init__(self):
        self._services = {}
        self._active_services = self._load_active_services()

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

    def register(self, name: str, init_func: Optional[Callable] = None, health_func: Optional[Callable] = None):
        """
        Register a service with its initialization and health check functions.
        """
        # If the service is not explicitly defined in settings, we default to True
        is_active = self._active_services.get(name, True)
        self._services[name] = {
            "init": init_func,
            "health": health_func,
            "active": is_active
        }

    def get_active_services(self) -> Dict[str, Dict[str, Any]]:
        return {name: data for name, data in self._services.items() if data["active"]}

    def get_all_services(self) -> Dict[str, Dict[str, Any]]:
        return self._services

service_registry = ServiceRegistry()
