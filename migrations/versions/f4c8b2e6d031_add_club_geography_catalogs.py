"""Add country and administrative area catalogs to clubs.

Revision ID: f4c8b2e6d031
Revises: d2a6f9c3e841
"""

from collections import Counter

from alembic import op
import sqlalchemy as sa


revision = "f4c8b2e6d031"
down_revision = "d2a6f9c3e841"
branch_labels = None
depends_on = None


VENEZUELA_ID = "10000000-0000-4000-8000-000000000001"
COLOMBIA_ID = "10000000-0000-4000-8000-000000000002"

COUNTRIES = (
    {
        "id": VENEZUELA_ID,
        "code": "VE",
        "name": "Venezuela",
        "is_active": True,
    },
    {
        "id": COLOMBIA_ID,
        "code": "CO",
        "name": "Colombia",
        "is_active": True,
    },
)

VENEZUELA_AREAS = (
    ("VE-Z", "Amazonas"),
    ("VE-B", "Anzoátegui"),
    ("VE-C", "Apure"),
    ("VE-D", "Aragua"),
    ("VE-E", "Barinas"),
    ("VE-F", "Bolívar"),
    ("VE-G", "Carabobo"),
    ("VE-H", "Cojedes"),
    ("VE-Y", "Delta Amacuro"),
    ("VE-W", "Dependencias Federales"),
    ("VE-A", "Distrito Capital"),
    ("VE-I", "Falcón"),
    ("VE-J", "Guárico"),
    ("VE-X", "La Guaira"),
    ("VE-K", "Lara"),
    ("VE-L", "Mérida"),
    ("VE-M", "Miranda"),
    ("VE-N", "Monagas"),
    ("VE-O", "Nueva Esparta"),
    ("VE-P", "Portuguesa"),
    ("VE-R", "Sucre"),
    ("VE-S", "Táchira"),
    ("VE-T", "Trujillo"),
    ("VE-U", "Yaracuy"),
    ("VE-V", "Zulia"),
)

COLOMBIA_AREAS = (
    ("CO-AMA", "Amazonas"),
    ("CO-ANT", "Antioquia"),
    ("CO-ARA", "Arauca"),
    ("CO-ATL", "Atlántico"),
    ("CO-DC", "Bogotá, D.C."),
    ("CO-BOL", "Bolívar"),
    ("CO-BOY", "Boyacá"),
    ("CO-CAL", "Caldas"),
    ("CO-CAQ", "Caquetá"),
    ("CO-CAS", "Casanare"),
    ("CO-CAU", "Cauca"),
    ("CO-CES", "Cesar"),
    ("CO-CHO", "Chocó"),
    ("CO-COR", "Córdoba"),
    ("CO-CUN", "Cundinamarca"),
    ("CO-GUA", "Guainía"),
    ("CO-GUV", "Guaviare"),
    ("CO-HUI", "Huila"),
    ("CO-LAG", "La Guajira"),
    ("CO-MAG", "Magdalena"),
    ("CO-MET", "Meta"),
    ("CO-NAR", "Nariño"),
    ("CO-NSA", "Norte de Santander"),
    ("CO-PUT", "Putumayo"),
    ("CO-QUI", "Quindío"),
    ("CO-RIS", "Risaralda"),
    ("CO-SAP", "San Andrés, Providencia y Santa Catalina"),
    ("CO-SAN", "Santander"),
    ("CO-SUC", "Sucre"),
    ("CO-TOL", "Tolima"),
    ("CO-VAC", "Valle del Cauca"),
    ("CO-VAU", "Vaupés"),
    ("CO-VID", "Vichada"),
)


def area_id(sequence):
    return f"20000000-0000-4000-8000-{sequence:012d}"


def build_area_rows():
    rows = []

    for index, (code, name) in enumerate(VENEZUELA_AREAS, start=1):
        rows.append({
            "id": area_id(index),
            "country_id": VENEZUELA_ID,
            "code": code,
            "name": name,
            "is_active": True,
        })

    for index, (code, name) in enumerate(COLOMBIA_AREAS, start=101):
        rows.append({
            "id": area_id(index),
            "country_id": COLOMBIA_ID,
            "code": code,
            "name": name,
            "is_active": True,
        })

    return rows


AREA_ROWS = build_area_rows()


def upgrade():
    op.create_table(
        "countries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False
        ),
        sa.CheckConstraint(
            "code = UPPER(code)",
            name="ck_countries_code_uppercase"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_countries_code")
    )

    op.create_table(
        "administrative_areas",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("country_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False
        ),
        sa.CheckConstraint(
            "code = UPPER(code)",
            name="ck_administrative_areas_code_uppercase"
        ),
        sa.ForeignKeyConstraint(
            ["country_id"],
            ["countries.id"],
            name="fk_administrative_areas_country_id_countries"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "country_id",
            "code",
            name="uq_administrative_areas_country_code"
        )
    )

    countries_table = sa.table(
        "countries",
        sa.column("id", sa.String(length=36)),
        sa.column("code", sa.String(length=2)),
        sa.column("name", sa.String(length=80)),
        sa.column("is_active", sa.Boolean())
    )
    areas_table = sa.table(
        "administrative_areas",
        sa.column("id", sa.String(length=36)),
        sa.column("country_id", sa.String(length=36)),
        sa.column("code", sa.String(length=10)),
        sa.column("name", sa.String(length=120)),
        sa.column("is_active", sa.Boolean())
    )

    op.bulk_insert(countries_table, list(COUNTRIES))
    op.bulk_insert(areas_table, AREA_ROWS)

    op.add_column(
        "clubs",
        sa.Column("country_id", sa.String(length=36), nullable=True)
    )
    op.add_column(
        "clubs",
        sa.Column(
            "administrative_area_id",
            sa.String(length=36),
            nullable=True
        )
    )
    op.add_column(
        "clubs",
        sa.Column("city", sa.String(length=120), nullable=True)
    )

    op.execute(
        sa.text(
            "UPDATE clubs SET city = TRIM(location) "
            "WHERE location IS NOT NULL AND TRIM(location) <> ''"
        )
    )

    name_counts = Counter(
        name.casefold()
        for _, name in VENEZUELA_AREAS + COLOMBIA_AREAS
    )

    for row in AREA_ROWS:
        if name_counts[row["name"].casefold()] != 1:
            continue

        safe_name = row["name"].replace("'", "''")
        op.execute(
            sa.text(
                "UPDATE clubs "
                f"SET country_id = '{row['country_id']}', "
                f"administrative_area_id = '{row['id']}' "
                "WHERE country_id IS NULL "
                "AND state IS NOT NULL "
                f"AND LOWER(TRIM(state)) = LOWER('{safe_name}')"
            )
        )

    with op.batch_alter_table("clubs") as batch_op:
        batch_op.create_foreign_key(
            "fk_clubs_country_id_countries",
            "countries",
            ["country_id"],
            ["id"]
        )
        batch_op.create_foreign_key(
            "fk_clubs_administrative_area_id_administrative_areas",
            "administrative_areas",
            ["administrative_area_id"],
            ["id"]
        )


def downgrade():
    with op.batch_alter_table("clubs") as batch_op:
        batch_op.drop_constraint(
            "fk_clubs_administrative_area_id_administrative_areas",
            type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_clubs_country_id_countries",
            type_="foreignkey"
        )
        batch_op.drop_column("city")
        batch_op.drop_column("administrative_area_id")
        batch_op.drop_column("country_id")

    op.drop_table("administrative_areas")
    op.drop_table("countries")
