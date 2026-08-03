from pydantic import BaseModel, Field


class ProductIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    category: str = Field(min_length=1, max_length=100)
    price: float = Field(ge=0, default=0)
    level: str | None = None
    is_active: bool = True


class ProductOut(BaseModel):
    id: int
    title: str
    description: str
    category: str
    price: float
    level: str | None
    is_active: bool
    vector_sync_status: str

    model_config = {"from_attributes": True}
