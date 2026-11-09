"""0001 initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-10 02:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # specialists table
    op.create_table(
        "specialists",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("specialty", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # clients table
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # rooms table
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_rooms_name"),
    )

    # sessions table
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("specialist_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="planned",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duration_minutes >= 15 AND duration_minutes <= 180 AND duration_minutes % 15 = 0",
            name="ck_sessions_duration",
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'done', 'cancelled')",
            name="ck_sessions_status",
        ),
        sa.ForeignKeyConstraint(
            ["specialist_id"],
            ["specialists.id"],
            name="fk_sessions_specialist_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name="fk_sessions_client_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name="fk_sessions_room_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_sessions_date_room", "sessions", ["session_date", "room_id"], unique=False)
    op.create_index(
        "ix_sessions_date_specialist",
        "sessions",
        ["session_date", "specialist_id"],
        unique=False,
    )
    op.create_index(
        "ix_sessions_date_client",
        "sessions",
        ["session_date", "client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_date_client", table_name="sessions")
    op.drop_index("ix_sessions_date_specialist", table_name="sessions")
    op.drop_index("ix_sessions_date_room", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("rooms")
    op.drop_table("clients")
    op.drop_table("specialists")
