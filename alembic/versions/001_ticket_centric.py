"""Restructure to ticket-centric model

Drop issued_tickets and reservations tables.
Create new tickets table with lifecycle states.

Revision ID: 001_ticket_centric
Revises:
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_ticket_centric"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old tables (order matters: issued_tickets depends on reservations)
    op.execute("DROP TABLE IF EXISTS issued_tickets CASCADE")
    op.execute("DROP TABLE IF EXISTS reservations CASCADE")

    # Drop old enum types
    op.execute("DROP TYPE IF EXISTS issued_ticket_status")
    op.execute("DROP TYPE IF EXISTS reservation_status")

    # Create new ticket_status enum
    ticket_status = postgresql.ENUM(
        "available", "reserved", "sold", "cancelled", "used",
        name="ticket_status",
        create_type=False,
    )
    ticket_status.create(op.get_bind(), checkfirst=True)

    # Create tickets table
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "ticket_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ticket_categories.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "available", "reserved", "sold", "cancelled", "used",
                name="ticket_status",
                create_type=False,
            ),
            nullable=False,
            server_default="available",
        ),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("external_reference", sa.String(255), nullable=True),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    # Drop tickets table and enum
    op.drop_table("tickets")
    op.execute("DROP TYPE IF EXISTS ticket_status")

    # Recreate old enum types
    reservation_status = postgresql.ENUM(
        "pending", "confirmed", "cancelled", "expired",
        name="reservation_status",
        create_type=False,
    )
    reservation_status.create(op.get_bind(), checkfirst=True)

    issued_ticket_status = postgresql.ENUM(
        "valid", "used", "cancelled",
        name="issued_ticket_status",
        create_type=False,
    )
    issued_ticket_status.create(op.get_bind(), checkfirst=True)

    # Recreate reservations table
    op.create_table(
        "reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ticket_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ticket_categories.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "confirmed", "cancelled", "expired",
                name="reservation_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("external_reference", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Recreate issued_tickets table
    op.create_table(
        "issued_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ticket_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ticket_categories.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reservation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reservations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "valid", "used", "cancelled",
                name="issued_ticket_status",
                create_type=False,
            ),
            nullable=False,
            server_default="valid",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
