"""Create the foundational sports catalog.

Revision ID: b4f10c2d9a71
Revises: a7d9e3c1b650
"""

from alembic import op
import sqlalchemy as sa


revision = "b4f10c2d9a71"
down_revision = "a7d9e3c1b650"
branch_labels = None
depends_on = None


SPORTS = (
    {
        "id": "00000000-0000-4000-8000-000000000001",
        "code": "VOLLEYBALL",
        "name": "Voleibol",
        "is_active": True,
    },
    {
        "id": "00000000-0000-4000-8000-000000000002",
        "code": "FOOTBALL",
        "name": "Fútbol",
        "is_active": False,
    },
    {
        "id": "00000000-0000-4000-8000-000000000003",
        "code": "BASEBALL",
        "name": "Béisbol",
        "is_active": False,
    },
)


def upgrade():
    op.create_table(
        "sports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False
        ),
        sa.CheckConstraint(
            "code = UPPER(code)",
            name="ck_sports_code_uppercase"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_sports_code")
    )

    sports_table = sa.table(
        "sports",
        sa.column("id", sa.String(length=36)),
        sa.column("code", sa.String(length=30)),
        sa.column("name", sa.String(length=80)),
        sa.column("is_active", sa.Boolean())
    )

    op.bulk_insert(sports_table, list(SPORTS))


def downgrade():
    op.drop_table("sports")
