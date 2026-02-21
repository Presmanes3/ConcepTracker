"""
Backward-compat shim — real implementation lives in src/registry/service_registry.py.
All new code should import from src.registry instead.
"""
from src.registry.service_registry import ServiceRegistry, service_registry  # noqa: F401
