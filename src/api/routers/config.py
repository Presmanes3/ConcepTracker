"""GET /config + PUT /config — LLM model and pricing settings."""
from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_bedrock_service, get_config_repo
from shared.schemas.api.config import ConfigResponse, ConfigUpdateRequest, ModelPricingSchema

router = APIRouter()


def _build_config_response(config_repo) -> ConfigResponse:
    settings = config_repo.get_settings()
    return ConfigResponse(
        active_model_id=settings.active_model_id,
        pricing={
            model_id: ModelPricingSchema(input=p.input, output=p.output)
            for model_id, p in settings.pricing.items()
        },
        is_configured=config_repo.is_configured,
        auto_pause_seconds=(
            settings.transcription.auto_pause_seconds
            if settings.transcription else 0
        ),
    )


@router.get("/config", response_model=ConfigResponse)
def get_config(config_repo=Depends(get_config_repo)):
    return _build_config_response(config_repo)


@router.put("/config", response_model=ConfigResponse)
def update_config(
    body: ConfigUpdateRequest,
    config_repo=Depends(get_config_repo),
    bedrock_svc=Depends(get_bedrock_service),
):
    if body.active_model_id is not None:
        # Validate model ID against Bedrock before saving
        valid, err = bedrock_svc.validate_model_id(body.active_model_id)
        if not valid:
            raise HTTPException(status_code=422, detail=f"Invalid model ID: {err}")
        config_repo.set_active_model(body.active_model_id)

    if body.model_pricing:
        for model_id, pricing in body.model_pricing.items():
            config_repo.set_model_pricing(model_id, pricing.input, pricing.output)

    return _build_config_response(config_repo)
