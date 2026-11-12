"""FastAPI router for Session operations (booking, conflicts, listing, status)."""

from datetime import date, time
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.domain.conflicts import ExistingSlot, NewSlot, find_conflicts
from app.domain.time_utils import (
    end_minutes,
    to_hhmm,
    to_minutes,
    validate_granularity_and_duration,
    validate_working_hours,
)
from app.models import Client, Room, Specialist
from app.models import Session as SessionModel
from app.schemas import (
    ConflictError,
    ErrorDetail,
    SessionCreate,
    SessionRead,
    SessionStatusUpdate,
)
from app.telemetry import get_tracer, record_booking_outcome

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

DbSession = Annotated[Session, Depends(get_db)]


def _format_time(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _serialize_session(
    sess: SessionModel,
    specialist_name: str,
    client_display_name: str,
    room_name: str,
) -> SessionRead:
    start_min = sess.start_time.hour * 60 + sess.start_time.minute
    end_min = end_minutes(start_min, sess.duration_minutes)
    end_str = to_hhmm(end_min)

    return SessionRead(
        id=sess.id,
        specialist_id=sess.specialist_id,
        specialist_name=specialist_name,
        client_id=sess.client_id,
        client_display_name=client_display_name,
        room_id=sess.room_id,
        room_name=room_name,
        session_date=sess.session_date,
        start_time=to_hhmm(start_min),
        end_time=end_str,
        duration_minutes=sess.duration_minutes,
        status=sess.status,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
    )


@router.get(
    "",
    response_model=list[SessionRead],
    summary="List all sessions for a given date sorted by room_id and start_time",
    operation_id="list_sessions",
)
def list_sessions(
    target_date: Annotated[date, Query(alias="date")],
    db: DbSession,
) -> list[SessionRead]:
    stmt = (
        select(SessionModel)
        .options(
            selectinload(SessionModel.specialist),
            selectinload(SessionModel.client),
            selectinload(SessionModel.room),
        )
        .filter(SessionModel.session_date == target_date)
        .order_by(SessionModel.room_id.asc(), SessionModel.start_time.asc())
    )
    results = db.scalars(stmt).all()
    return [
        _serialize_session(
            s,
            s.specialist.name if s.specialist else "Unknown",
            s.client.display_name if s.client else "Unknown",
            s.room.name if s.room else "Unknown",
        )
        for s in results
    ]


@router.post(
    "",
    response_model=SessionRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorDetail, "description": "Referenced entity does not exist"},
        409: {"model": ConflictError, "description": "Booking conflict with existing session"},
    },
    summary="Book a new session if no conflict exists",
    operation_id="create_session",
)
def create_session(request: Request, payload: SessionCreate, db: DbSession) -> Response:
    started = perf_counter()
    with get_tracer().start_as_current_span(
        "booking.create",
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            # 1. Parse times and validate domain rules (BR-1, BR-2)
            start_min = to_minutes(payload.start_time)
            end_min = end_minutes(start_min, payload.duration_minutes)

            try:
                validate_working_hours(start_min, end_min)
                validate_granularity_and_duration(start_min, payload.duration_minutes)
            except ValueError as err:
                record_booking_outcome(
                    result="invalid",
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    duration_seconds=perf_counter() - started,
                    span=span,
                    duration_minutes=payload.duration_minutes,
                    room_id=payload.room_id,
                    specialist_id=payload.specialist_id,
                )
                request.state.booking_telemetry_recorded = True
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
                ) from err

            # 2. Acquire Date-Scoped Advisory Lock inside transaction (BR-8)
            date_str = payload.session_date.isoformat()
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(CAST(:date_str AS text)))"),
                {"date_str": date_str},
            )

            # 3. Verify referenced specialist, client, room exist (AC-2.4)
            spec = db.get(Specialist, payload.specialist_id)
            cl = db.get(Client, payload.client_id)
            rm = db.get(Room, payload.room_id)
            if not spec or not cl or not rm:
                record_booking_outcome(
                    result="not_found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    duration_seconds=perf_counter() - started,
                    span=span,
                    duration_minutes=payload.duration_minutes,
                    room_id=payload.room_id,
                    specialist_id=payload.specialist_id,
                )
                request.state.booking_telemetry_recorded = True
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

            # 4. Query active sessions on this date (BR-5: ignore cancelled)
            existing_sessions = list(
                db.scalars(
                    select(SessionModel).filter(
                        SessionModel.session_date == payload.session_date,
                        SessionModel.status != "cancelled",
                        or_(
                            SessionModel.specialist_id == payload.specialist_id,
                            SessionModel.room_id == payload.room_id,
                            SessionModel.client_id == payload.client_id,
                        ),
                    )
                ).all()
            )

            existing_slots = [
                ExistingSlot(
                    session_id=s.id,
                    start_minutes=to_minutes(_format_time(s.start_time)),
                    duration_minutes=s.duration_minutes,
                    specialist_id=s.specialist_id,
                    client_id=s.client_id,
                    room_id=s.room_id,
                    status=s.status,
                )
                for s in existing_sessions
            ]

            new_slot = NewSlot(
                start_minutes=start_min,
                duration_minutes=payload.duration_minutes,
                specialist_id=payload.specialist_id,
                client_id=payload.client_id,
                room_id=payload.room_id,
            )

            conflicts = find_conflicts(new_slot, existing_slots)
            if conflicts:
                conflict_types = ",".join(sorted({c.type for c in conflicts}))
                record_booking_outcome(
                    result="conflict",
                    status_code=status.HTTP_409_CONFLICT,
                    duration_seconds=perf_counter() - started,
                    span=span,
                    conflict_types=conflict_types,
                    duration_minutes=payload.duration_minutes,
                    room_id=payload.room_id,
                    specialist_id=payload.specialist_id,
                )
                request.state.booking_telemetry_recorded = True
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content={
                        "detail": "conflict",
                        "conflicts": [
                            {
                                "type": c.type,
                                "session_id": c.conflicting_session_id,
                                "conflicting_session_id": c.conflicting_session_id,
                            }
                            for c in conflicts
                        ],
                    },
                )

            # 5. Persist the new session
            new_start_time = time(start_min // 60, start_min % 60)
            session_obj = SessionModel(
                specialist_id=payload.specialist_id,
                client_id=payload.client_id,
                room_id=payload.room_id,
                session_date=payload.session_date,
                start_time=new_start_time,
                duration_minutes=payload.duration_minutes,
                status="planned",
            )
            db.add(session_obj)
            db.commit()
            db.refresh(session_obj)

            response_data = _serialize_session(session_obj, spec.name, cl.display_name, rm.name)
            record_booking_outcome(
                result="created",
                status_code=status.HTTP_201_CREATED,
                duration_seconds=perf_counter() - started,
                span=span,
                conflict_types="",
                duration_minutes=payload.duration_minutes,
                room_id=payload.room_id,
                specialist_id=payload.specialist_id,
            )
            request.state.booking_telemetry_recorded = True
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=response_data.model_dump(mode="json"),
            )
        except HTTPException:
            raise
        except Exception as exc:
            record_booking_outcome(
                result="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                duration_seconds=perf_counter() - started,
                span=span,
                duration_minutes=payload.duration_minutes,
                room_id=payload.room_id,
                specialist_id=payload.specialist_id,
                error_type=type(exc).__name__,
            )
            request.state.booking_telemetry_recorded = True
            raise


@router.patch(
    "/{session_id}",
    response_model=SessionRead,
    responses={
        404: {"model": ErrorDetail, "description": "Session not found"},
        409: {"model": ErrorDetail, "description": "Invalid status transition"},
    },
    summary="Transition a planned session to done or cancelled",
    operation_id="update_session_status",
)
def update_session_status(
    session_id: int,
    payload: SessionStatusUpdate,
    db: DbSession,
) -> SessionRead:
    session_obj = db.get(SessionModel, session_id)
    if not session_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    # Only allow transition from planned (BR-5, AC-4.1)
    if session_obj.status != "planned":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="invalid_status_transition"
        )

    session_obj.status = payload.status
    db.commit()
    db.refresh(session_obj)

    spec = db.get(Specialist, session_obj.specialist_id)
    cl = db.get(Client, session_obj.client_id)
    rm = db.get(Room, session_obj.room_id)

    return _serialize_session(
        session_obj,
        spec.name if spec else "Unknown",
        cl.display_name if cl else "Unknown",
        rm.name if rm else "Unknown",
    )
