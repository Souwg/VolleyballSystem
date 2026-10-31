from flask import jsonify, request
from flask_jwt_extended import jwt_required

from src.api.api_blueprint import api
from src.api.models import (
    MatchPlayer,
    MatchSession,
    Player,
    PlayerMatchStat,
    Team,
    TeamPlayer,
)
from src.api.sports import (
    InvalidClubSportError,
    SportAdapterNotFoundError,
    get_club_sport_adapter,
)
from src.api.season_service import resolve_season_for_read
from src.api.utils import error_response, get_current_user


PLAYABLE_MATCH_STATUSES = ["present", "late"]


def performance_not_supported_error():
    return error_response(
        (
            "El deporte del club no tiene métricas de rendimiento "
            "válidas configuradas."
        ),
        "PLAYER_PERFORMANCE_NOT_SUPPORTED",
        409
    )


def get_performance_contract(adapter):
    if not adapter.capabilities.supports_player_stats:
        raise NotImplementedError

    stat_fields = adapter.get_performance_stat_fields()
    metric_fields = adapter.get_performance_metric_fields()

    for fields in (stat_fields, metric_fields):
        if (
            not isinstance(fields, tuple)
            or not fields
            or any(
                not isinstance(field, str) or not field.strip()
                for field in fields
            )
            or len(set(fields)) != len(fields)
        ):
            raise ValueError

    if (
        "points_total" not in metric_fields
        or "errors_total" not in metric_fields
        or any(
            not hasattr(PlayerMatchStat, field)
            for field in stat_fields
        )
    ):
        raise ValueError

    return stat_fields, metric_fields


def calculate_performance_metrics(
    adapter,
    stats,
    metric_fields,
):
    metrics = adapter.calculate_performance_metrics(stats)

    if (
        not isinstance(metrics, dict)
        or set(metrics) != set(metric_fields)
        or any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in metrics.values()
        )
    ):
        raise ValueError

    return metrics


@api.route("/players/<string:player_id>/performance", methods=["GET"])
@jwt_required()
def get_player_performance(player_id):
    user = get_current_user()

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Deportista no encontrada",
            "PLAYER_NOT_FOUND",
            404
        )

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para consultar rendimiento",
            "FORBIDDEN",
            403
        )

    season, season_error, _ = resolve_season_for_read(
        user.club_id,
        request.args.get("season_id"),
        default_to_active=False,
    )

    if season_error:
        return error_response(*season_error)

    try:
        sport_adapter = get_club_sport_adapter(player.club)
        stat_fields, metric_fields = get_performance_contract(
            sport_adapter
        )
        calculate_performance_metrics(
            sport_adapter,
            {field: 0 for field in stat_fields},
            metric_fields,
        )
    except (
        InvalidClubSportError,
        SportAdapterNotFoundError,
        ArithmeticError,
        AttributeError,
        LookupError,
        NotImplementedError,
        TypeError,
        ValueError,
    ):
        return performance_not_supported_error()

    # Solo partidos en los que realmente pudo participar y jugó.
    match_query = (
        MatchPlayer.query
        .join(
            MatchSession,
            MatchSession.id == MatchPlayer.match_id
        )
        .join(
            Team,
            Team.id == MatchSession.team_id
        )
        .filter(
            MatchPlayer.player_id == player.id,
            MatchPlayer.did_play.is_(True),
            MatchPlayer.attendance_status.in_(
                PLAYABLE_MATCH_STATUSES
            ),
            Team.club_id == user.club_id
        )
    )

    if season:
        match_query = match_query.filter(Team.season_id == season.id)

    match_rows = (
        match_query.order_by(
            MatchSession.date.desc(),
            MatchPlayer.created_at.desc()
        )
        .all()
    )

    totals = {
        field: 0
        for field in stat_fields
    }

    matches = []
    official_matches = []
    provisional_matches = []
    matches_with_stats = 0

    def safe_value(value):
        return int(value or 0)

    for row in match_rows:
        match = row.match
        stat = row.performance_stats

        match_stats = {
            key: 0
            for key in totals.keys()
        }

        if stat:
            for key in totals.keys():
                value = safe_value(getattr(stat, key, 0))

                match_stats[key] = value

        try:
            match_metrics = calculate_performance_metrics(
                sport_adapter,
                match_stats,
                metric_fields,
            )
        except (
            ArithmeticError,
            AttributeError,
            LookupError,
            NotImplementedError,
            TypeError,
            ValueError,
        ):
            return performance_not_supported_error()

        serialized_match = {
            "match_player_id": row.id,
            "match_id": match.id,
            "date": (
                match.date.isoformat()
                if match.date else None
            ),
            "opponent_name": match.opponent_name,
            "match_type": match.match_type,
            "location": match.location,
            "result": match.result,
            "home_sets": match.home_sets,
            "opponent_sets": match.opponent_sets,
            "is_completed": match.is_completed,
            "team": {
                "id": match.team.id,
                "name": match.team.name
            },
            "player_number": row.player_number,
            "position": (
                row.position
                or player.main_position
            ),
            "points_total": match_metrics["points_total"],
            "errors_total": match_metrics["errors_total"],
            "stats": match_stats
        }

        matches.append(serialized_match)

        if match.is_completed:
            official_matches.append(serialized_match)

            if stat:
                matches_with_stats += 1

                for key in totals.keys():
                    totals[key] += match_stats[key]
        else:
            provisional_matches.append(serialized_match)

    matches_played = len(official_matches)

    try:
        summary_metrics = calculate_performance_metrics(
            sport_adapter,
            totals,
            metric_fields,
        )
    except (
        ArithmeticError,
        AttributeError,
        LookupError,
        NotImplementedError,
        TypeError,
        ValueError,
    ):
        return performance_not_supported_error()

    membership_query = TeamPlayer.query.join(Team).filter(
        TeamPlayer.player_id == player.id,
        Team.club_id == user.club_id,
    )

    if season:
        membership_query = membership_query.filter(
            Team.season_id == season.id
        )

    memberships = membership_query.order_by(
        TeamPlayer.joined_at.desc()
    ).all()

    return jsonify({
        "player": {
            "id": player.id,
            "first_name": player.first_name,
            "last_name": player.last_name,
            "main_position": player.main_position
        },
        "summary": {
            "matches_played": matches_played,
            "matches_with_stats": matches_with_stats,
            **summary_metrics,
        },
        "totals": totals,
        "season": season.serialize() if season else None,
        "memberships": [
            {
                **membership.serialize(),
                "team": membership.team.serialize(),
                "season": membership.team.season.serialize(),
            }
            for membership in memberships
        ],
        # Se conserva `matches` para mantener compatible el contrato previo.
        "matches": matches,
        "official_matches": official_matches,
        "provisional_matches": provisional_matches
    }), 200
