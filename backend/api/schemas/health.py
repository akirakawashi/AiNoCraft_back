from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Service status")
