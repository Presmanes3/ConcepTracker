import yaml
import os
import threading
from typing import Optional, Dict

from shared.schemas.models.config import AppSettings, ModelPricing

CONFIG_FILE = os.path.join("config", "settings.yaml")

class ConfigRepository:
    """
    Singleton repository for managing persistent application settings.
    Sourced from config/settings.yaml.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConfigRepository, cls).__new__(cls)
                cls._instance._settings: AppSettings = AppSettings()
                cls._instance.refresh()
        return cls._instance

    def refresh(self):
        """Reload settings from disk into memory."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = yaml.safe_load(f)
                    if data:
                        self._settings = AppSettings.model_validate(data)
                    else:
                        self._settings = AppSettings()
            except (yaml.YAMLError, IOError, ValueError):
                # Fallback to empty if file is corrupt or invalid
                self._settings = AppSettings()
        else:
            self._settings = AppSettings()

    def save(self):
        """Persist current in-memory settings to disk."""
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            # Using model_dump for YAML serialization
            yaml.safe_dump(self._settings.model_dump(), f, sort_keys=False, default_flow_style=False)

    def get_settings(self) -> AppSettings:
        """Retrieves the current SSoT for application settings."""
        return self._settings

    def set_model_pricing(self, model_id: str, input_price: float, output_price: float):
        """Update or create pricing for a specific model and persist changes."""
        self._settings.pricing[model_id] = ModelPricing(
            input=input_price, 
            output=output_price
        )
        self.save()

    def set_active_model(self, model_id: str):
        """Set the active model ID and persist change."""
        self._settings.active_model_id = model_id
        # Also ensure it exists in pricing if it's new
        if model_id not in self._settings.pricing:
            self._settings.pricing[model_id] = ModelPricing()
        self.save()

    def get_active_model_id(self) -> str:
        """Retrieves the ID of the currently active model."""
        return self._settings.active_model_id

    @property
    def is_configured(self) -> bool:
        """Helper to check if any pricing is actually defined."""
        return len(self._settings.pricing) > 0

# Singleton instance
config_repository = ConfigRepository()
