"""Simplify ticket lifecycle: remove sold/used, add confirmed; drop user-facing fields

- Replace ticket_status enum: remove 'sold' and 'used', add 'confirmed'
- Drop columns: sold_at, used_at, customer_email, user_id
- Add column: confirmed_at
- Add index on external_reference

Revision ID: 002_confirm_flow
Revises: 001_ticket_centric
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_confirm_flow"
down_revision: Union[str, None] = "001_ticket_centric"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop columns that no longer exist
    op.drop_column("tickets", "sold_at")
    op.drop_column("tickets", "used_at")
    op.drop_column("tickets", "customer_email")

    # 2. Add new column
    op.add_column(
        "tickets",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Add index on external_reference
    op.create_index("ix_tickets_external_reference", "tickets", ["external_reference"])

    # 4. Alter the ticket_status enum: remove 'sold'/'used', add 'confirmed'
    #    PostgreSQL does not support removing values from an enum, so we
    #    recreate the type.
    op.execute("ALTER TYPE ticket_status RENAME TO ticket_status_old")
    op.execute(
        "CREATE TYPE ticket_status AS ENUM ('available', 'reserved', 'confirmed', 'cancelled')"
    )

    # Migrate any existing 'sold' tickets to 'confirmed', 'used' tickets to 'confirmed'
    op.execute(
        "UPDATE tickets SET status = 'confirmed' "
        "WHERE status IN ('sold', 'used')"
    )

    # Switch column to the new type
    op.execute(
        "ALTER TABLE tickets "
        "ALTER COLUMN status TYPE ticket_status USING status::text::ticket_status"
    )
    op.execute(
        "ALTER TABLE tickets ALTER COLUMN status SET DEFAULT 'available'"
    )

    # Drop old enum
    op.execute("DROP TYPE ticket_status_old")


def downgrade() -> None:
    # Reverse: recreate old enum, restore columns, drop new columns/indexes

    # 1. Rename current enum, recreate old one
    op.execute("ALTER TYPE ticket_status RENAME TO ticket_status_new")
    op.execute(
        "CREATE TYPE ticket_status AS ENUM "
        "('available', 'reserved', 'sold', 'cancelled', 'used')"
    )

    # Migrate confirmed → sold
    op.execute(
        "UPDATE tickets SET status = 'sold' WHERE status = 'confirmed'"
    )

    op.execute(
        "ALTER TABLE tickets "
        "ALTER COLUMN status TYPE ticket_status USING status::text::ticket_status"
    )
    op.execute(
        "ALTER TABLE tickets ALTER COLUMN status SET DEFAULT 'available'"
    )
    op.execute("DROP TYPE ticket_status_new")

    # 2. Drop new index
    op.drop_index("ix_tickets_external_reference", table_name="tickets")

    # 3. Drop new column
    op.drop_column("tickets", "confirmed_at")

    # 4. Restore old columns
    op.add_column(
        "tickets",
        sa.Column("customer_email", sa.String(255), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
