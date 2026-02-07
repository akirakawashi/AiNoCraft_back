from sqlalchemy import MetaData
from sqlmodel import SQLModel


class BaseModel(SQLModel):
    metadata = MetaData()
