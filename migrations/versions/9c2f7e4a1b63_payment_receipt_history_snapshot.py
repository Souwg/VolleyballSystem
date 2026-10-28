"""Preserve receipt history and financial snapshots.

Revision ID: 9c2f7e4a1b63
Revises: e8c41f7a9d30
"""

from alembic import op
import sqlalchemy as sa


revision = "9c2f7e4a1b63"
down_revision = "e8c41f7a9d30"
branch_labels = None
depends_on = None


PAYMENT_TYPE_LABELS = {
    "enrollment": "Inscripción",
    "monthly": "Mensualidad",
    "uniform": "Uniforme",
    "tournament": "Inscripción de torneo",
    "referee": "Arbitraje",
    "extra": "Extra",
}

NAMING_CONVENTION = {
    "uq": "uq_%(table_name)s_%(column_0_name)s"
}


def _get_payment_id_unique_constraint(bind):
    constraints = sa.inspect(bind).get_unique_constraints(
        "payment_receipts"
    )

    for constraint in constraints:
        if constraint.get("column_names") == ["payment_id"]:
            return (
                constraint.get("name")
                or "uq_payment_receipts_payment_id"
            )

    raise RuntimeError(
        "No se encontró la restricción única histórica de payment_id"
    )


def _backfill_existing_receipts(bind):
    metadata = sa.MetaData()
    receipts = sa.Table(
        "payment_receipts",
        metadata,
        autoload_with=bind
    )
    payments = sa.Table(
        "player_payments",
        metadata,
        autoload_with=bind
    )
    players = sa.Table(
        "players",
        metadata,
        autoload_with=bind
    )
    clubs = sa.Table(
        "clubs",
        metadata,
        autoload_with=bind
    )

    existing_receipts = bind.execute(
        sa.select(
            receipts.c.id,
            receipts.c.payment_id,
            receipts.c.player_id,
            receipts.c.club_id
        )
    ).mappings().all()

    for receipt in existing_receipts:
        payment = bind.execute(
            sa.select(payments).where(
                payments.c.id == receipt["payment_id"]
            )
        ).mappings().first()

        player = bind.execute(
            sa.select(players).where(
                players.c.id == receipt["player_id"]
            )
        ).mappings().first()

        club = bind.execute(
            sa.select(clubs).where(
                clubs.c.id == receipt["club_id"]
            )
        ).mappings().first()

        player_name = None
        if player:
            player_name = " ".join(
                value
                for value in [
                    player.get("first_name"),
                    player.get("last_name")
                ]
                if value
            ) or None

        payment_type = payment.get("payment_type") if payment else None
        concept = (
            PAYMENT_TYPE_LABELS.get(payment_type, "Pago")
            if payment_type
            else None
        )

        bind.execute(
            receipts.update()
            .where(receipts.c.id == receipt["id"])
            .values(
                status="issued",
                snapshot_source="legacy_backfill",
                amount_snapshot=(
                    payment.get("amount") if payment else None
                ),
                payment_type_snapshot=payment_type,
                concept_snapshot=concept,
                period_start_snapshot=(
                    payment.get("period_start") if payment else None
                ),
                period_end_snapshot=(
                    payment.get("period_end") if payment else None
                ),
                payment_date_snapshot=(
                    payment.get("payment_date") if payment else None
                ),
                payment_method_snapshot=(
                    payment.get("payment_method") if payment else None
                ),
                reference_snapshot=(
                    payment.get("reference") if payment else None
                ),
                player_name_snapshot=player_name,
                club_name_snapshot=(
                    club.get("name") if club else None
                ),
                club_location_snapshot=(
                    club.get("location") if club else None
                ),
                club_state_snapshot=(
                    club.get("state") if club else None
                ),
                primary_color_snapshot=(
                    club.get("primary_color") if club else None
                ),
                secondary_color_snapshot=(
                    club.get("secondary_color") if club else None
                ),
                logo_url_snapshot=(
                    club.get("image_url") if club else None
                )
            )
        )


def upgrade():
    bind = op.get_bind()
    payment_id_unique = _get_payment_id_unique_constraint(bind)

    with op.batch_alter_table(
        "payment_receipts",
        naming_convention=NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint(
            payment_id_unique,
            type_="unique"
        )
        batch_op.add_column(sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="issued"
        ))
        batch_op.add_column(sa.Column(
            "invalidated_at",
            sa.DateTime(),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "invalidated_by",
            sa.String(length=36),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "invalidation_reason",
            sa.String(length=80),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "snapshot_source",
            sa.String(length=30),
            nullable=False,
            server_default="issued"
        ))
        batch_op.add_column(sa.Column(
            "amount_snapshot",
            sa.Numeric(precision=10, scale=2),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "payment_type_snapshot",
            sa.String(length=30),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "concept_snapshot",
            sa.String(length=120),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "period_start_snapshot",
            sa.Date(),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "period_end_snapshot",
            sa.Date(),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "payment_date_snapshot",
            sa.Date(),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "payment_method_snapshot",
            sa.String(length=50),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "reference_snapshot",
            sa.String(length=120),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "player_name_snapshot",
            sa.String(length=200),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "club_name_snapshot",
            sa.String(length=120),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "club_location_snapshot",
            sa.String(length=120),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "club_state_snapshot",
            sa.String(length=120),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "primary_color_snapshot",
            sa.String(length=20),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "secondary_color_snapshot",
            sa.String(length=20),
            nullable=True
        ))
        batch_op.add_column(sa.Column(
            "logo_url_snapshot",
            sa.String(length=500),
            nullable=True
        ))
        batch_op.create_foreign_key(
            "fk_payment_receipts_invalidated_by_users",
            "users",
            ["invalidated_by"],
            ["id"]
        )
        batch_op.create_check_constraint(
            "ck_payment_receipts_status",
            "status IN ('issued', 'invalidated')"
        )
        batch_op.create_check_constraint(
            "ck_payment_receipts_snapshot_source",
            "snapshot_source IN ('issued', 'legacy_backfill')"
        )

    _backfill_existing_receipts(bind)

    op.create_index(
        "uq_payment_receipts_issued_payment",
        "payment_receipts",
        ["payment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'issued'"),
        sqlite_where=sa.text("status = 'issued'")
    )


def downgrade():
    bind = op.get_bind()
    duplicate_payment = bind.execute(sa.text("""
        SELECT payment_id
        FROM payment_receipts
        GROUP BY payment_id
        HAVING COUNT(*) > 1
        LIMIT 1
    """)).first()

    if duplicate_payment:
        raise RuntimeError(
            "No se puede restaurar la relación 0..1 mientras existan "
            "múltiples recibos históricos para un mismo pago"
        )

    op.drop_index(
        "uq_payment_receipts_issued_payment",
        table_name="payment_receipts"
    )

    with op.batch_alter_table(
        "payment_receipts",
        naming_convention=NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint(
            "ck_payment_receipts_snapshot_source",
            type_="check"
        )
        batch_op.drop_constraint(
            "ck_payment_receipts_status",
            type_="check"
        )
        batch_op.drop_constraint(
            "fk_payment_receipts_invalidated_by_users",
            type_="foreignkey"
        )
        batch_op.drop_column("logo_url_snapshot")
        batch_op.drop_column("secondary_color_snapshot")
        batch_op.drop_column("primary_color_snapshot")
        batch_op.drop_column("club_state_snapshot")
        batch_op.drop_column("club_location_snapshot")
        batch_op.drop_column("club_name_snapshot")
        batch_op.drop_column("player_name_snapshot")
        batch_op.drop_column("reference_snapshot")
        batch_op.drop_column("payment_method_snapshot")
        batch_op.drop_column("payment_date_snapshot")
        batch_op.drop_column("period_end_snapshot")
        batch_op.drop_column("period_start_snapshot")
        batch_op.drop_column("concept_snapshot")
        batch_op.drop_column("payment_type_snapshot")
        batch_op.drop_column("amount_snapshot")
        batch_op.drop_column("snapshot_source")
        batch_op.drop_column("invalidation_reason")
        batch_op.drop_column("invalidated_by")
        batch_op.drop_column("invalidated_at")
        batch_op.drop_column("status")
        batch_op.create_unique_constraint(
            "uq_payment_receipts_payment_id",
            ["payment_id"]
        )
