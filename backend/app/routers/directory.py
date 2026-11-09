"""FastAPI router for Studio Directory operations (specialists, clients, rooms)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Room, Specialist
from app.models import Session as SessionModel
from app.schemas import (
    ClientCreate,
    ClientRead,
    ErrorDetail,
    RoomCreate,
    RoomRead,
    SpecialistCreate,
    SpecialistRead,
)

router = APIRouter(prefix="/api", tags=["directory"])

DbSession = Annotated[Session, Depends(get_db)]


# ==========================================
# Specialists Endpoints
# ==========================================
@router.get(
    "/specialists",
    response_model=list[SpecialistRead],
    summary="List all specialists sorted alphabetically by name",
    operation_id="list_specialists",
)
def list_specialists(db: DbSession) -> list[Specialist]:
    stmt = select(Specialist).order_by(Specialist.name.asc())
    return list(db.scalars(stmt).all())


@router.post(
    "/specialists",
    response_model=SpecialistRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new specialist",
    operation_id="create_specialist",
)
def create_specialist(payload: SpecialistCreate, db: DbSession) -> Specialist:
    specialist = Specialist(name=payload.name, specialty=payload.specialty)
    db.add(specialist)
    db.commit()
    db.refresh(specialist)
    return specialist


@router.delete(
    "/specialists/{specialist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorDetail, "description": "Specialist not found"},
        409: {"model": ErrorDetail, "description": "Specialist has planned or existing sessions"},
    },
    summary="Delete a specialist if not referenced by sessions",
    operation_id="delete_specialist",
)
def delete_specialist(specialist_id: int, db: DbSession) -> Response:
    specialist = db.get(Specialist, specialist_id)
    if not specialist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    # Check for linked sessions (BR-6)
    has_sessions = db.execute(
        select(SessionModel.id).filter_by(specialist_id=specialist_id).limit(1)
    ).scalar_one_or_none()
    if has_sessions is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="has_planned_sessions")

    db.delete(specialist)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# Clients Endpoints
# ==========================================
@router.get(
    "/clients",
    response_model=list[ClientRead],
    summary="List all clients sorted alphabetically by display_name",
    operation_id="list_clients",
)
def list_clients(db: DbSession) -> list[Client]:
    stmt = select(Client).order_by(Client.display_name.asc())
    return list(db.scalars(stmt).all())


@router.post(
    "/clients",
    response_model=ClientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new client",
    operation_id="create_client",
)
def create_client(payload: ClientCreate, db: DbSession) -> Client:
    client = Client(display_name=payload.display_name)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.delete(
    "/clients/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorDetail, "description": "Client not found"},
        409: {"model": ErrorDetail, "description": "Client has planned or existing sessions"},
    },
    summary="Delete a client if not referenced by sessions",
    operation_id="delete_client",
)
def delete_client(client_id: int, db: DbSession) -> Response:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    # Check for linked sessions (BR-6)
    has_sessions = db.execute(
        select(SessionModel.id).filter_by(client_id=client_id).limit(1)
    ).scalar_one_or_none()
    if has_sessions is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="has_planned_sessions")

    db.delete(client)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# Rooms Endpoints
# ==========================================
@router.get(
    "/rooms",
    response_model=list[RoomRead],
    summary="List all rooms sorted alphabetically by name",
    operation_id="list_rooms",
)
def list_rooms(db: DbSession) -> list[Room]:
    stmt = select(Room).order_by(Room.name.asc())
    return list(db.scalars(stmt).all())


@router.post(
    "/rooms",
    response_model=RoomRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorDetail, "description": "Room name already exists"},
    },
    summary="Create a new room",
    operation_id="create_room",
)
def create_room(payload: RoomCreate, db: DbSession) -> Room:
    # Check for unique room name (BR-7)
    existing = db.execute(
        select(Room.id).filter_by(name=payload.name).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="room_name_taken")

    room = Room(name=payload.name)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.delete(
    "/rooms/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorDetail, "description": "Room not found"},
        409: {"model": ErrorDetail, "description": "Room has planned or existing sessions"},
    },
    summary="Delete a room if not referenced by sessions",
    operation_id="delete_room",
)
def delete_room(room_id: int, db: DbSession) -> Response:
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    # Check for linked sessions (BR-6)
    has_sessions = db.execute(
        select(SessionModel.id).filter_by(room_id=room_id).limit(1)
    ).scalar_one_or_none()
    if has_sessions is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="has_planned_sessions")

    db.delete(room)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
