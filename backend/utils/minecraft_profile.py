import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

from backend.api.schemas.minecraft import MinecraftProfile, MinecraftProperty, MinecraftUserInfo
from backend.config import avatar_config, minio_settings
from backend.database.tables import User


class MinecraftProfileService:
    @staticmethod
    def create_client_token() -> str:
        return uuid4().hex

    @staticmethod
    def get_profile_id(user: User) -> str:
        return user.user_id.hex

    @classmethod
    def build_profile(cls, user: User) -> MinecraftProfile:
        return MinecraftProfile(id=cls.get_profile_id(user), name=user.login)

    @classmethod
    def build_properties(cls, user: User) -> list[MinecraftProperty]:
        if not user.avatar_name:
            return []

        skin_url = f"{minio_settings.public_url}/{avatar_config.bucket_name}/{user.user_id}/{user.avatar_name}"
        textures = {
            "timestamp": int(datetime.now(tz=UTC).timestamp() * 1000),
            "profileId": cls.get_profile_id(user),
            "profileName": user.login,
            "textures": {"SKIN": {"url": skin_url}},
        }
        encoded = base64.b64encode(json.dumps(textures, separators=(",", ":")).encode()).decode()

        return [MinecraftProperty(name="textures", value=encoded)]

    @classmethod
    def build_user_info(cls, user: User) -> MinecraftUserInfo:
        return MinecraftUserInfo(id=cls.get_profile_id(user), properties=cls.build_properties(user))
