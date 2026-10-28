from flask import jsonify
from flask_jwt_extended import jwt_required

from src.api.api_blueprint import api
from src.api.models import MatchPlayer, MatchSession, Player, Team
from src.api.utils import error_response, get_current_user


PLAYABLE_MATCH_STATUSES = ["present", "late"]


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

    # Solo partidos en los que realmente pudo participar y jugó.
    match_rows = (
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
        .order_by(
            MatchSession.date.desc(),
            MatchPlayer.created_at.desc()
        )
        .all()
    )

    totals = {
        "attacks_total": 0,
        "attacks_positive": 0,
        "attacks_neutral": 0,
        "attacks_errors": 0,

        "receptions_total": 0,
        "receptions_positive": 0,
        "receptions_neutral": 0,
        "receptions_negative": 0,

        "defenses_total": 0,
        "defenses_positive": 0,
        "defenses_neutral": 0,
        "defenses_negative": 0,

        "sets_total": 0,
        "sets_positive": 0,
        "sets_neutral": 0,
        "sets_errors": 0,

        "serves_total": 0,
        "serves_in": 0,
        "serves_aces": 0,
        "serves_errors": 0,

        "blocks_total": 0,
        "blocks_points": 0,
        "blocks_neutral": 0,
        "blocks_errors": 0,
    }

    matches = []
    official_matches = []
    provisional_matches = []
    matches_with_stats = 0

    def safe_value(value):
        return int(value or 0)

    def percentage(value, total):
        if total <= 0:
            return 0

        return round((value / total) * 100)

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

        points_total = (
            match_stats["attacks_positive"]
            + match_stats["serves_aces"]
            + match_stats["blocks_points"]
        )

        errors_total = (
            match_stats["attacks_errors"]
            + match_stats["sets_errors"]
            + match_stats["serves_errors"]
            + match_stats["blocks_errors"]
        )

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
            "points_total": points_total,
            "errors_total": errors_total,
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

    points_total = (
        totals["attacks_positive"]
        + totals["serves_aces"]
        + totals["blocks_points"]
    )

    errors_total = (
        totals["attacks_errors"]
        + totals["sets_errors"]
        + totals["serves_errors"]
        + totals["blocks_errors"]
    )

    actions_total = (
        totals["attacks_total"]
        + totals["receptions_total"]
        + totals["defenses_total"]
        + totals["sets_total"]
        + totals["serves_total"]
        + totals["blocks_total"]
    )

    attack_efficiency = 0

    if totals["attacks_total"] > 0:
        attack_efficiency = round(
            (
                (
                    totals["attacks_positive"]
                    - totals["attacks_errors"]
                )
                / totals["attacks_total"]
            )
            * 100
        )

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
            "actions_total": actions_total,
            "points_total": points_total,
            "errors_total": errors_total,

            "attack_efficiency": attack_efficiency,

            "attack_positive_rate": percentage(
                totals["attacks_positive"],
                totals["attacks_total"]
            ),

            "reception_positive_rate": percentage(
                totals["receptions_positive"],
                totals["receptions_total"]
            ),

            "defense_positive_rate": percentage(
                totals["defenses_positive"],
                totals["defenses_total"]
            ),

            "set_positive_rate": percentage(
                totals["sets_positive"],
                totals["sets_total"]
            ),

            "serve_ace_rate": percentage(
                totals["serves_aces"],
                totals["serves_total"]
            ),

            "block_point_rate": percentage(
                totals["blocks_points"],
                totals["blocks_total"]
            )
        },
        "totals": totals,
        # Se conserva `matches` para mantener compatible el contrato previo.
        "matches": matches,
        "official_matches": official_matches,
        "provisional_matches": provisional_matches
    }), 200
