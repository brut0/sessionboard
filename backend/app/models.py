"""SQLAlchemy 2.x ORM models for SessionBoard."""

from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Specialist(Base):
    __tablename__ = "specialists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="specialist", passive_deletes="all"
    )


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="client", passive_deletes="all"
    )


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("name", name="uq_rooms_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="room", passive_deletes="all"
    )


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes >= 15 AND duration_minutes <= 180 AND duration_minutes % 15 = 0",
            name="ck_sessions_duration",
        ),
        CheckConstraint(
            "status IN ('planned', 'done', 'cancelled')",
            name="ck_sessions_status",
        ),
        Index("ix_sessions_date_room", "session_date", "room_id"),
        Index("ix_sessions_date_specialist", "session_date", "specialist_id"),
        Index("ix_sessions_date_client", "session_date", "client_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialist_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("specialists.id", ondelete="RESTRICT", name="fk_sessions_specialist_id"),
        nullable=False,
    )
    client_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("clients.id", ondelete="RESTRICT", name="fk_sessions_client_id"),
        nullable=False,
    )
    room_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rooms.id", ondelete="RESTRICT", name="fk_sessions_room_id"),
        nullable=False,
    )
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="planned", server_default="planned"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    specialist: Mapped["Specialist"] = relationship("Specialist", back_populates="sessions")
    client: Mapped["Client"] = relationship("Client", back_populates="sessions")
    room: Mapped["Room"] = relationship("Room", back_populates="sessions")
