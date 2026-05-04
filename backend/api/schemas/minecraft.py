from pydantic import BaseModel, Field


class MinecraftAgent(BaseModel):
    name: str = Field(default="Minecraft")
    version: int = Field(default=1)


class MinecraftProperty(BaseModel):
    name: str
    value: str
    signature: str | None = None


class MinecraftProfile(BaseModel):
    id: str = Field(description="UUID without dashes")
    name: str


class MinecraftUserInfo(BaseModel):
    id: str
    properties: list[MinecraftProperty] = Field(default_factory=list)


class MinecraftAuthenticateRequest(BaseModel):
    username: str
    password: str
    clientToken: str | None = None
    requestUser: bool = False
    agent: MinecraftAgent = Field(default_factory=MinecraftAgent)


class MinecraftRefreshRequest(BaseModel):
    accessToken: str | None = None
    refreshToken: str | None = None
    clientToken: str | None = None
    requestUser: bool = False
    selectedProfile: MinecraftProfile | None = None


class MinecraftValidateRequest(BaseModel):
    accessToken: str
    clientToken: str | None = None


class MinecraftInvalidateRequest(BaseModel):
    accessToken: str | None = None
    refreshToken: str | None = None
    clientToken: str | None = None


class MinecraftSignoutRequest(BaseModel):
    username: str
    password: str


class MinecraftAuthResponse(BaseModel):
    accessToken: str
    refreshToken: str
    clientToken: str
    availableProfiles: list[MinecraftProfile]
    selectedProfile: MinecraftProfile
    user: MinecraftUserInfo | None = None


class MinecraftJoinRequest(BaseModel):
    accessToken: str
    selectedProfile: str = Field(description="UUID without dashes")
    serverId: str


class MinecraftHasJoinedResponse(BaseModel):
    id: str
    name: str
    properties: list[MinecraftProperty] = Field(default_factory=list)


class MinecraftApiRootResponse(BaseModel):
    meta: dict[str, str | int | dict[str, str]]
    skinDomains: list[str]
