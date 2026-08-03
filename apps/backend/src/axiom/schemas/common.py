from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: int
    page: int
    per_page: int
    has_more: bool


class DataEnvelope(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    data: T


class ListEnvelope(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    data: list[T]
    meta: PaginationMeta


class FieldError(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    message: str


class ErrorBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    details: dict[str, list[FieldError]] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    error: ErrorBody
