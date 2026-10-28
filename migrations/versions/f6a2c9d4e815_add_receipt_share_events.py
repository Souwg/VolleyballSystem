"""Add immutable receipt share event history.

Revision ID: f6a2c9d4e815
Revises: 9c2f7e4a1b63
"""

import uuid

from alembic import op
import sqlalchemy as sa


revision = "f6a2c9d4e815"
down_revision = "9c2f7e4a1b63"
branch_labels = None
depends_on = None


def _backfill_legacy_share_metadata(bind):
    metadata = sa.MetaData()
    receipts = sa.Table(
        "payment_receipts",
        metadata,
        autoload_with=bind
    )
    share_events = sa.Table(
        "payment_receipt_share_events",
        metadata,
        autoload_with=bind
    )

    legacy_receipts = bind.execute(
        sa.select(
            receipts.c.id,
            receipts.c.club_id,
            receipts.c.sent_at,
            receipts.c.sent_channel,
            receipts.c.sent_to
        ).where(receipts.c.sent_at.is_not(None))
    ).mappings().all()

    for receipt in legacy_receipts:
        bind.execute(
            share_events.insert().values(
                id=str(uuid.uuid4()),
                receipt_id=receipt["id"],
                club_id=receipt["club_id"],
                channel=receipt["sent_channel"],
                destination=receipt["sent_to"],
                event_type="legacy_share_metadata",
                source="legacy_sent_metadata",
                created_at=receipt["sent_at"],
                created_by=None
            )
        )


def upgrade():
    op.create_table(
        "payment_receipt_share_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("receipt_id", sa.String(length=36), nullable=False),
        sa.Column("club_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=True),
        sa.Column("destination", sa.String(length=120), nullable=True),
        sa.Column(
            "event_type",
            sa.String(length=40),
            nullable=False,
            server_default="share_initiated"
        ),
        sa.Column(
            "source",
            sa.String(length=40),
            nullable=False,
            server_default="application"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('share_initiated', 'legacy_share_metadata')",
            name="ck_receipt_share_events_event_type"
        ),
        sa.CheckConstraint(
            "source IN ('application', 'legacy_sent_metadata')",
            name="ck_receipt_share_events_source"
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name="fk_receipt_share_events_club_id_clubs"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_receipt_share_events_created_by_users"
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["payment_receipts.id"],
            name="fk_receipt_share_events_receipt_id_payment_receipts"
        ),
        sa.PrimaryKeyConstraint("id")
    )

    op.create_index(
        "ix_receipt_share_events_receipt_created_at",
        "payment_receipt_share_events",
        ["receipt_id", "created_at"],
        unique=False
    )
    op.create_index(
        "uq_receipt_share_events_legacy_receipt",
        "payment_receipt_share_events",
        ["receipt_id"],
        unique=True,
        postgresql_where=sa.text("source = 'legacy_sent_metadata'"),
        sqlite_where=sa.text("source = 'legacy_sent_metadata'")
    )

    _backfill_legacy_share_metadata(op.get_bind())


def downgrade():
    op.drop_index(
        "uq_receipt_share_events_legacy_receipt",
        table_name="payment_receipt_share_events"
    )
    op.drop_index(
        "ix_receipt_share_events_receipt_created_at",
        table_name="payment_receipt_share_events"
    )
    op.drop_table("payment_receipt_share_events")
