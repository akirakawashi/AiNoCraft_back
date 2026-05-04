from urllib.parse import urlparse

from fastapi import APIRouter

from backend.api.schemas.minecraft import MinecraftApiRootResponse
from backend.config import minio_settings

router = APIRouter(tags=["minecraft"])


@router.get("/", response_model=MinecraftApiRootResponse, include_in_schema=False)
async def minecraft_api_root() -> MinecraftApiRootResponse:
    parsed = urlparse(minio_settings.public_url)
    skin_domain = parsed.hostname or minio_settings.public_url
    return MinecraftApiRootResponse(
        meta={
            "serverName": "AiNoCraft Yggdrasil",
            "implementationName": "ainocraft-auth",
            "implementationVersion": 1,
            "links": {},
        },
        skinDomains=[skin_domain],
    )
