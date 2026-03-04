import yaml
import os
from pathlib import Path
from typing import List, Dict, Any, Optional


def _resolve_settings_path() -> Path:
    env_path = os.environ.get("CONCEPTRACKER_CONFIG")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parent.parent.parent / "config" / "settings.yaml"


class AudioDeviceService:
    """
    Single Source of Truth (SSoT) for audio device configuration and availability.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AudioDeviceService, cls).__new__(cls)
        return cls._instance

    @property
    def _settings_path(self) -> Path:
        return _resolve_settings_path()

    def get_available_input_devices(self) -> List[Dict[str, Any]]:
        """Returns a list of available audio input devices."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = []
            for i, device in enumerate(devices):
                if device.get('max_input_channels', 0) > 0:
                    input_devices.append({
                        "id": i,
                        "name": device.get('name', f"Device {i}"),
                        "channels": device.get('max_input_channels'),
                        "default": i == sd.default.device[0]
                    })
            return input_devices
        except ImportError:
            return []
        except Exception as e:
            print(f"Error querying audio devices: {e}")
            return []

    def get_configured_device_id(self) -> Optional[int]:
        """Reads the configured input device ID from settings.yaml."""
        if not self._settings_path.exists():
            return None
        try:
            with open(self._settings_path, "r") as f:
                settings = yaml.safe_load(f) or {}
                return settings.get("audio", {}).get("input_device_id")
        except Exception:
            return None

    def set_configured_device_id(self, device_id: int) -> bool:
        """Saves the selected input device ID to settings.yaml."""
        try:
            settings = {}
            if self._settings_path.exists():
                with open(self._settings_path, "r") as f:
                    settings = yaml.safe_load(f) or {}
            
            if "audio" not in settings:
                settings["audio"] = {}
            
            settings["audio"]["input_device_id"] = device_id
            
            with open(self._settings_path, "w") as f:
                yaml.safe_dump(settings, f, default_flow_style=False)
            return True
        except Exception as e:
            print(f"Error saving audio device configuration: {e}")
            return False

    def is_device_available(self, device_id: int) -> bool:
        """Checks if a specific device ID is currently available as an input device."""
        devices = self.get_available_input_devices()
        return any(d["id"] == device_id for d in devices)

    def get_default_device_id(self) -> Optional[int]:
        """Returns the system's default input device ID."""
        devices = self.get_available_input_devices()
        for d in devices:
            if d.get("default"):
                return d["id"]
        return devices[0]["id"] if devices else None

audio_device_service = AudioDeviceService()
