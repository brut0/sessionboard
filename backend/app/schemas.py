"""Pydantic schemas for request validation and serialization."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ErrorDetail(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "error"]


class VersionResponse(BaseModel):
    version: str
    env: Literal["local", "dev", "prod", "test"]


class ConflictItem(BaseModel):
    type: Literal["specialist", "room", "client"]
    session_id: int
    conflicting_session_id: int | None = None


class ConflictError(BaseModel):
    detail: str = "conflict"
    conflicts: list[ConflictItem]


# --- Specialist Schemas ---
class SpecialistCreate(BaseModel):
    name: str = Field(..., max_length=100)
    specialty: str = Field(..., max_length=100)

    @field_validator("name", "specialty")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field cannot be blank or whitespace-only (BR-9)")
        return trimmed


class SpecialistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    specialty: str
    created_at: datetime


# --- Client Schemas ---
class ClientCreate(BaseModel):
    display_name: str = Field(..., max_length=100)

    @field_validator("display_name")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field cannot be blank or whitespace-only (BR-9)")
        return trimmed


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    created_at: datetime


# --- Room Schemas ---
class RoomCreate(BaseModel):
    name: str = Field(..., max_length=50)

    @field_validator("name")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field cannot be blank or whitespace-only (BR-9)")
        return trimmed


class RoomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime


# --- Session Schemas ---
class SessionCreate(BaseModel):
    specialist_id: int
    client_id: int
    room_id: int
    session_date: date
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    duration_minutes: int


class SessionStatusUpdate(BaseModel):
    status: Literal["done", "cancelled"]


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    specialist_id: int
    specialist_name: str
    client_id: int
    client_display_name: str
    room_id: int
    room_name: str
    session_date: date
    start_time: str
    end_time: str
    duration_minutes: int
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
