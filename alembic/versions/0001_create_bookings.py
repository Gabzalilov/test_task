"""create bookings table

Revision ID: 0001_create_bookings
Revises:
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_create_bookings"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service_type", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "confirmed", "failed", name="booking_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bookings_status", "bookings", ["status"])
    op.create_index("ix_bookings_created_at", "bookings", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_bookings_created_at", table_name="bookings")
    op.drop_index("ix_bookings_status", table_name="bookings")
    op.drop_table("bookings")
