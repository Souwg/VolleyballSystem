
import click

from src.api.models import Club, db, User
from src.api.payment_service import (
    execute_monthly_sync,
)
from src.api.time_utils import get_club_today


def _sync_monthly_payments_for_club(club, as_of):
    plan, result = execute_monthly_sync(
        club=club,
        as_of=as_of
    )

    db.session.commit()

    return plan, result

"""
In this file, you can add as many commands as you want using the @app.cli.command decorator
Flask commands are usefull to run cronjobs or tasks outside of the API but sill in integration 
with youy database, for example: Import the price of bitcoin every night as 12am
"""
def setup_commands(app):
    
    """ 
    This is an example command "insert-test-users" that you can run from the command line
    by typing: $ flask insert-test-users 5
    Note: 5 is the number of users to add
    """
    @app.cli.command("insert-test-users") # name of our command
    @click.argument("count") # argument of out command
    def insert_test_users(count):
        print("Creating test users")
        for x in range(1, int(count) + 1):
            user = User()
            user.email = "test_user" + str(x) + "@test.com"
            user.password = "123456"
            user.is_active = True
            db.session.add(user)
            db.session.commit()
            print("User: ", user.email, " created.")

        print("All test users created")

    @app.cli.command("insert-test-data")
    def insert_test_data():
        pass

    @app.cli.command("sync-monthly-payments")
    @click.option(
        "--club-id",
        type=str,
        help="Sincroniza únicamente el Club indicado."
    )
    @click.option(
        "--all",
        "all_clubs",
        is_flag=True,
        help="Sincroniza todos los Clubs activos."
    )
    def sync_monthly_payments_command(club_id, all_clubs):
        """Sincroniza obligaciones mensuales mediante una ejecución explícita."""
        if bool(club_id) == bool(all_clubs):
            raise click.UsageError(
                "Debes indicar exactamente una opción: --club-id o --all."
            )

        totals = {
            "clubs_processed": 0,
            "clubs_skipped": 0,
            "payments_created": 0,
            "payments_marked_overdue": 0,
            "players_skipped_inactive": 0,
            "warnings": 0,
            "errors": 0
        }

        click.echo("SportFlow monthly payment sync")

        if club_id:
            club = Club.query.get(club_id)

            if not club:
                raise click.ClickException(
                    f"Club no encontrado: {club_id}"
                )

            clubs = [club]
        else:
            clubs = Club.query.order_by(
                Club.created_at.asc()
            ).all()

        for club in clubs:
            if club.access_status != "active":
                totals["clubs_skipped"] += 1
                click.echo(
                    f"Club {club.id}: omitido porque está suspendido."
                )
                continue

            try:
                as_of = get_club_today(club)
                plan, result = _sync_monthly_payments_for_club(
                    club=club,
                    as_of=as_of
                )
            except Exception:
                db.session.rollback()
                totals["errors"] += 1
                app.logger.exception(
                    "Falló la sincronización mensual del club %s",
                    club.id
                )
                click.echo(
                    f"Club {club.id}: error durante la sincronización.",
                    err=True
                )

                if club_id:
                    raise click.ClickException(
                        "La sincronización no pudo completarse."
                    )

                continue

            result_summary = result["summary"]
            plan_summary = plan["summary"]

            totals["clubs_processed"] += 1
            totals["payments_created"] += result_summary[
                "payments_created"
            ]
            totals["payments_marked_overdue"] += result_summary[
                "payments_marked_overdue"
            ]
            totals["players_skipped_inactive"] += plan_summary[
                "players_skipped_inactive"
            ]
            totals["warnings"] += len(plan["warnings"])

            click.echo(
                (
                    f"Club {club.id}: "
                    f"fecha local={as_of.isoformat()}, "
                    f"mensualidades creadas={result_summary['payments_created']}, "
                    f"pagos vencidos={result_summary['payments_marked_overdue']}, "
                    f"inactivas omitidas={plan_summary['players_skipped_inactive']}, "
                    f"advertencias={len(plan['warnings'])}."
                )
            )

        click.echo("")
        click.echo(f"Clubs procesados: {totals['clubs_processed']}")
        click.echo(f"Clubs omitidos: {totals['clubs_skipped']}")
        click.echo(
            f"Mensualidades creadas: {totals['payments_created']}"
        )
        click.echo(
            "Pagos marcados vencidos: "
            f"{totals['payments_marked_overdue']}"
        )
        click.echo(
            "Jugadoras inactivas omitidas: "
            f"{totals['players_skipped_inactive']}"
        )
        click.echo(
            f"Configuraciones con advertencia: {totals['warnings']}"
        )
        click.echo(f"Errores: {totals['errors']}")

        if totals["errors"]:
            raise click.ClickException(
                "Una o más sincronizaciones no pudieron completarse."
            )
