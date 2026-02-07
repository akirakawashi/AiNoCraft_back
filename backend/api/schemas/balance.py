from pydantic import BaseModel, Field


class BalanceResponse(BaseModel):
    loli_coins: int = Field(description="Number of loli coins balance")
    loli_crystal: int = Field(description="Number of loli crystals balance")
