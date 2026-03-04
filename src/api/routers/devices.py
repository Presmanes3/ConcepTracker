"""GET /devices — list audio input devices; PUT /devices/active — set active device."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_audio_device_service
from shared.schemas.api.transcription import DeviceResponse, DeviceSetRequest
from shared.schemas.api.common import MessageResponse

router = APIRouter()


@router.get("/devices", response_model=List[DeviceResponse])
def list_devices(svc=Depends(get_audio_device_service)):
    devices = svc.get_available_input_devices()
    configured_id = svc.get_configured_device_id()
    return [
        DeviceResponse(
            id=d["id"],
            name=d["name"],
            channels=d["channels"],
            default=d.get("default", False),
            active=(d["id"] == configured_id),
        )
        for d in devices
    ]


@router.put("/devices/active", response_model=MessageResponse)
def set_active_device(body: DeviceSetRequest, svc=Depends(get_audio_device_service)):
    """Set the active device ID in configuration.
    
    Note: Validation against local devices is skipped because the API may be
    running in a container while the CLI (with the actual hardware) is remote.
    """
    success = svc.set_configured_device_id(body.device_id)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to persist device {body.device_id} to configuration.")
    return MessageResponse(message=f"Active device ID set to {body.device_id} in configuration.")
