from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from src.api.api_blueprint import api
from src.api.models import (
    db,
    MatchEvent,
    MatchPlayer,
    MatchSession,
    MatchSubstitution,
    Player,
    PlayerMatchStat,
    PlayerPayment,
    Team,
    TeamPlayer,
    TournamentPlayer,
    TournamentTeam,
)
from src.api.payment_charge_helpers import (
    add_charge_if_absent,
    parse_money,
    split_money_exactly,
)
from src.api.sports import (
    InvalidClubSportError,
    SportAdapterNotFoundError,
    get_club_sport_adapter,
)
from src.api.stats_validator import validate_match_stats
from src.api.utils import error_response, get_current_user

VALID_MATCH_STATUSES = ["present", "late", "absent", "injured"]
PLAYABLE_MATCH_STATUSES = ["present", "late"]
VALID_MATCH_STEPS = [0, 1, 2, 3, 4]
VALID_MATCH_TYPES = ["official", "friendly", "scrimmage"]
VALID_MATCH_CAPTURE_MODES = ["live", "summary"]


def _get_match_lineup_size(match):
    try:
        sport_adapter = get_club_sport_adapter(match.team.club)
    except (InvalidClubSportError, SportAdapterNotFoundError):
        return None

    capabilities = getattr(sport_adapter, "capabilities", None)
    lineup_size = getattr(capabilities, "lineup_size", None)

    if (
        not getattr(capabilities, "supports_lineup", False)
        or isinstance(lineup_size, bool)
        or not isinstance(lineup_size, int)
        or lineup_size <= 0
    ):
        return None

    return lineup_size


def _get_match_period_range(match):
    try:
        sport_adapter = get_club_sport_adapter(match.team.club)
    except (InvalidClubSportError, SportAdapterNotFoundError):
        return None

    capabilities = getattr(sport_adapter, "capabilities", None)
    period_min = getattr(capabilities, "period_min", None)
    period_max = getattr(capabilities, "period_max", None)

    if (
        not getattr(capabilities, "supports_periods", False)
        or isinstance(period_min, bool)
        or isinstance(period_max, bool)
        or not isinstance(period_min, int)
        or not isinstance(period_max, int)
        or period_min > period_max
    ):
        return None

    return period_min, period_max


def _validate_match_event(match, action, result):
    try:
        sport_adapter = get_club_sport_adapter(match.team.club)
        return sport_adapter.validate_event(action, result)
    except (
        InvalidClubSportError,
        SportAdapterNotFoundError,
        NotImplementedError,
    ):
        return None


def _validate_match_result(match, home_value, opponent_value):
    try:
        sport_adapter = get_club_sport_adapter(match.team.club)
        return sport_adapter.validate_match_result(home_value, opponent_value)
    except (
        InvalidClubSportError,
        SportAdapterNotFoundError,
        NotImplementedError,
    ):
        return None, None


def match_has_valid_result(match, validated_result=None):
    if not match or match.result not in ["win", "loss"]:
        return False

    if validated_result is None:
        validated_result, validation_error = _validate_match_result(
            match,
            match.home_sets,
            match.opponent_sets
        )

        if validation_error:
            return False

    if validated_result is None:
        return False

    return match.result == validated_result.result





def match_player_has_sports_history(match_player):
    if not match_player:
        return False

    if MatchEvent.query.filter_by(
        match_player_id=match_player.id
    ).first():
        return True

    if PlayerMatchStat.query.filter_by(
        match_player_id=match_player.id
    ).first():
        return True

    return MatchSubstitution.query.filter(
        (
            MatchSubstitution.player_out_id
            == match_player.id
        )
        |
        (
            MatchSubstitution.player_in_id
            == match_player.id
        )
    ).first() is not None


def match_has_recorded_game_history(match_id):
    if MatchEvent.query.filter_by(match_id=match_id).first():
        return True

    if MatchSubstitution.query.filter_by(match_id=match_id).first():
        return True

    return (
        PlayerMatchStat.query
        .join(
            MatchPlayer,
            MatchPlayer.id == PlayerMatchStat.match_player_id
        )
        .filter(MatchPlayer.match_id == match_id)
        .first()
        is not None
    )


def match_has_statistical_data(match_id):
    if MatchEvent.query.filter_by(match_id=match_id).first():
        return True

    return (
        PlayerMatchStat.query
        .join(
            MatchPlayer,
            MatchPlayer.id == PlayerMatchStat.match_player_id
        )
        .filter(MatchPlayer.match_id == match_id)
        .first()
        is not None
    )


def capture_mode_write_error(match, required_mode):
    if match.capture_mode == required_mode:
        return None

    if match.capture_mode is None:
        if match_has_statistical_data(match.id):
            return error_response(
                (
                    "Este partido tiene estadísticas históricas sin un modo "
                    "de captura verificable y no admite nuevas escrituras."
                ),
                "MATCH_CAPTURE_MODE_LEGACY_LOCKED",
                409
            )

        return error_response(
            "Elige cómo registrarás las estadísticas de este partido.",
            "MATCH_CAPTURE_MODE_REQUIRED",
            409
        )

    if required_mode == "live":
        return error_response(
            "Los eventos no están disponibles en el modo resumen.",
            "MATCH_EVENTS_NOT_AVAILABLE",
            409
        )

    return error_response(
        "Las estadísticas de este partido se generan desde LiveMatch.",
        "MATCH_STATS_MANAGED_BY_LIVE",
        409
    )



def sync_match_roster_if_open(match):
    """
    Reconcilia el snapshot del partido mientras la convocatoria
    todavía no ha sido guardada.

    Partido normal:
    - Incluye únicamente membresías activas del equipo.
    - La deportista debe estar activa.

    Partido de torneo:
    - Además debe estar inscrita activamente en TournamentPlayer.

    Cuando match_step deja de ser 0, el snapshot queda congelado
    para conservar el historial.
    """

    if not match:
        return 0

    if match.match_step != 0:
        return 0

    if match.is_completed:
        return 0

    # =========================
    # 1. Determinar elegibles
    # =========================

    eligible_memberships_query = (
        TeamPlayer.query
        .join(
            Player,
            Player.id == TeamPlayer.player_id
        )
        .filter(
            TeamPlayer.team_id == match.team_id,
            TeamPlayer.status == "active",
            Player.is_active.is_(True)
        )
    )

    if match.tournament_team_id:
        active_tournament_player_ids = (
            db.session.query(TournamentPlayer.player_id)
            .filter(
                TournamentPlayer.tournament_team_id
                == match.tournament_team_id,
                TournamentPlayer.status == "active"
            )
        )

        eligible_memberships_query = (
            eligible_memberships_query
            .filter(
                TeamPlayer.player_id.in_(
                    active_tournament_player_ids
                )
            )
        )

    eligible_memberships = eligible_memberships_query.all()

    eligible_by_player_id = {
        membership.player_id: membership
        for membership in eligible_memberships
    }

    eligible_player_ids = set(eligible_by_player_id.keys())

    # =========================
    # 2. Leer snapshot actual
    # =========================

    existing_rows = MatchPlayer.query.filter_by(
        match_id=match.id
    ).all()

    existing_by_player_id = {
        row.player_id: row
        for row in existing_rows
    }

    existing_player_ids = set(existing_by_player_id.keys())

    added_count = 0
    removed_count = 0
    updated_count = 0

    # =========================
    # 3. Agregar quienes faltan
    # =========================

    player_ids_to_add = (
        eligible_player_ids - existing_player_ids
    )

    for player_id in player_ids_to_add:
        membership = eligible_by_player_id[player_id]

        snapshot = MatchPlayer(
            match_id=match.id,
            player_id=membership.player_id,
            player_number=membership.player_number,
            is_called=False,
            attendance_status=None,
            did_play=False,
            is_on_court=False,
            position=None
        )

        db.session.add(snapshot)
        added_count += 1

    # =========================
    # 4. Actualizar el número
    # =========================

    player_ids_to_keep = (
        eligible_player_ids & existing_player_ids
    )

    for player_id in player_ids_to_keep:
        row = existing_by_player_id[player_id]
        membership = eligible_by_player_id[player_id]

        if row.player_number != membership.player_number:
            row.player_number = membership.player_number
            updated_count += 1

    # =========================
    # 5. Retirar no elegibles
    # =========================

    player_ids_to_remove = (
        existing_player_ids - eligible_player_ids
    )

    for player_id in player_ids_to_remove:
        row = existing_by_player_id[player_id]

        # Protección defensiva:
        # aunque match_step sea 0, no eliminamos una fila que ya
        # tenga señales de historial o participación.
        has_history = (
            row.is_called
            or row.attendance_status is not None
            or row.did_play
            or row.is_on_court
            or bool(row.events)
            or row.performance_stats is not None
        )

        if has_history:
            continue

        db.session.delete(row)
        removed_count += 1

    total_changes = (
        added_count +
        removed_count +
        updated_count
    )

    if total_changes > 0:
        db.session.commit()

    return total_changes

def recalculate_player_match_stats(match_player_id):
    row = MatchPlayer.query.get(match_player_id)

    if not row:
        return

    stat = PlayerMatchStat.query.filter_by(
        match_player_id=match_player_id
    ).first()

    if not stat:
        stat = PlayerMatchStat(match_player_id=match_player_id)
        db.session.add(stat)


    events = MatchEvent.query.filter_by(
        match_player_id=match_player_id
    ).all()

    # Reset stats
    stat.attacks_total = 0
    stat.attacks_positive = 0
    stat.attacks_neutral = 0
    stat.attacks_errors = 0

    stat.receptions_total = 0
    stat.receptions_positive = 0
    stat.receptions_neutral = 0
    stat.receptions_negative = 0

    stat.defenses_total = 0
    stat.defenses_positive = 0
    stat.defenses_neutral = 0
    stat.defenses_negative = 0

    stat.sets_total = 0
    stat.sets_positive = 0
    stat.sets_neutral = 0
    stat.sets_errors = 0

    stat.serves_total = 0
    stat.serves_in = 0
    stat.serves_aces = 0
    stat.serves_errors = 0

    stat.blocks_total = 0
    stat.blocks_points = 0
    stat.blocks_neutral = 0
    stat.blocks_errors = 0


    for event in events:
        action = event.action_type
        result = event.result

        if action == "attack":
            stat.attacks_total += 1

            if result == "positive":
                stat.attacks_positive += 1
            elif result == "neutral":
                stat.attacks_neutral += 1
            elif result == "error":
                stat.attacks_errors += 1

        elif action == "reception":
            stat.receptions_total += 1

            if result == "positive":
                stat.receptions_positive += 1
            elif result == "neutral":
                stat.receptions_neutral += 1
            elif result == "negative":
                stat.receptions_negative += 1

        elif action == "defense":
            stat.defenses_total += 1

            if result == "positive":
                stat.defenses_positive += 1
            elif result == "neutral":
                stat.defenses_neutral += 1
            elif result == "negative":
                stat.defenses_negative += 1

        elif action == "set":
            stat.sets_total += 1

            if result == "positive":
                stat.sets_positive += 1
            elif result == "neutral":
                stat.sets_neutral += 1
            elif result == "error":
                stat.sets_errors += 1

        elif action == "serve":
            stat.serves_total += 1

            if result == "ace":
                stat.serves_aces += 1
            elif result == "in":
                stat.serves_in += 1
            elif result == "error":
                stat.serves_errors += 1

        elif action == "block":
            stat.blocks_total += 1

            if result == "point":
                stat.blocks_points += 1
            elif result == "neutral":
                stat.blocks_neutral += 1
            elif result == "error":
                stat.blocks_errors += 1


############################################# MATCHES #############################################

@api.route("/matches", methods=["POST"])
@jwt_required()
def create_match():
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para crear partidos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    body = request.get_json() or {}

    team_id = body.get("team_id")
    date = body.get("date")
    opponent_name = body.get("opponent_name")
    match_type = body.get("match_type", "official")
    location = body.get("location")
    notes = body.get("notes")

    # Nuevos campos
    tournament_team_id = body.get("tournament_team_id")
    referee_fee = body.get("referee_fee")

    if opponent_name:
        opponent_name = " ".join(
            str(opponent_name).strip().split()
        )

    if location:
        location = " ".join(
            str(location).strip().split()
        )

    if notes:
        notes = str(notes).strip()

    if not team_id:
        return error_response(
            "El equipo es obligatorio",
            "TEAM_ID_REQUIRED",
            400
        )

    if match_type not in VALID_MATCH_TYPES:
        return error_response(
            "Tipo de partido inválido",
            "INVALID_MATCH_TYPE",
            400
        )

    if not date:
        return error_response(
            "La fecha es obligatoria",
            "MATCH_DATE_REQUIRED",
            400
        )

    try:
        parsed_date = datetime.strptime(
            date,
            "%Y-%m-%d"
        ).date()
    except (ValueError, TypeError):
        return error_response(
            "Formato de fecha inválido. Usa YYYY-MM-DD",
            "INVALID_DATE_FORMAT",
            400
        )

    if not opponent_name:
        return error_response(
            "El rival es obligatorio",
            "OPPONENT_NAME_REQUIRED",
            400
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este equipo",
            "FORBIDDEN",
            403
        )

    tournament_team = None

    if tournament_team_id:
        tournament_team = TournamentTeam.query.get(
            tournament_team_id
        )

        if not tournament_team:
            return error_response(
                "Participación de torneo no encontrada",
                "TOURNAMENT_TEAM_NOT_FOUND",
                404
            )

        if tournament_team.tournament.club_id != user.club_id:
            return error_response(
                "No tienes acceso a esta participación",
                "FORBIDDEN",
                403
            )

        if tournament_team.team_id != team.id:
            return error_response(
                "La participación seleccionada no corresponde a este equipo",
                "TOURNAMENT_TEAM_MISMATCH",
                400
            )

        if tournament_team.status != "active":
            return error_response(
                "La participación del equipo no está activa",
                "TOURNAMENT_TEAM_NOT_ACTIVE",
                409
            )

        if tournament_team.tournament.status != "active":
            return error_response(
                "El torneo no está activo",
                "TOURNAMENT_NOT_ACTIVE",
                409
            )

    parsed_referee_fee = None

    if referee_fee not in [None, ""]:
        parsed_referee_fee, amount_error = parse_money(
            referee_fee,
            "El costo de arbitraje"
        )

        if amount_error:
            return amount_error

    elif tournament_team:
        parsed_referee_fee = (
            tournament_team.tournament.default_referee_fee
        )

    match = MatchSession(
        team_id=team.id,
        tournament_team_id=(
            tournament_team.id
            if tournament_team
            else None
        ),
        referee_fee=parsed_referee_fee,
        date=parsed_date,
        opponent_name=opponent_name,
        match_type=match_type,
        location=location or None,
        notes=notes or None,
        created_by=user.id
    )

    db.session.add(match)
    db.session.flush()

    roster_query = (
        TeamPlayer.query
        .join(
            Player,
            Player.id == TeamPlayer.player_id
        )
        .filter(
            TeamPlayer.team_id == team.id,
            TeamPlayer.status == "active",
            Player.is_active.is_(True)
        )
    )

    if tournament_team:
        active_tournament_player_ids = (
            db.session.query(TournamentPlayer.player_id)
            .filter(
                TournamentPlayer.tournament_team_id == tournament_team.id,
                TournamentPlayer.status == "active"
            )
        )

        roster_query = roster_query.filter(
            TeamPlayer.player_id.in_(
                active_tournament_player_ids
            )
        )

    roster_members = roster_query.all()

    for member in roster_members:
        snapshot = MatchPlayer(
            match_id=match.id,
            player_id=member.player_id,
            player_number=member.player_number,
            is_called=False,
            attendance_status=None,
            did_play=False,
            is_on_court=False,
            position=None
        )

        db.session.add(snapshot)

    db.session.commit()

    return jsonify({
        "message": "Partido creado correctamente",
        "match": match.serialize()
    }), 201

@api.route("/teams/<string:team_id>/matches", methods=["GET"])
@jwt_required()
def get_team_matches(team_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta categoría",
            "FORBIDDEN",
            403
        )

    matches = MatchSession.query.filter_by(team_id=team.id)\
        .order_by(MatchSession.date.desc())\
        .all()

    return jsonify({
        "team": team.serialize(),
        "total_matches": len(matches),
        "matches": [m.serialize() for m in matches]
    }), 200

@api.route("/matches/<string:match_id>/roster", methods=["POST"])
@jwt_required()
def save_match_roster(match_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este partido",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}
    players = body.get("players")

    if not players:
        return error_response(
            "Debes seleccionar al menos una jugadora",
            "MATCH_ROSTER_REQUIRED",
            400
        )

    if not isinstance(players, list):
        return error_response(
            "La convocatoria enviada no es válida",
            "INVALID_MATCH_ROSTER",
            400
        )

    selected_player_ids = []

    for item in players:
        if not isinstance(item, dict):
            return error_response(
                "La convocatoria enviada no es válida",
                "INVALID_MATCH_ROSTER",
                400
            )

        player_id = item.get("player_id")

        if not isinstance(player_id, str) or not player_id.strip():
            return error_response(
                "La convocatoria enviada no es válida",
                "INVALID_MATCH_ROSTER",
                400
            )

        selected_player_ids.append(player_id)

    selected_ids = set(selected_player_ids)

    if len(selected_ids) != len(selected_player_ids):
        return error_response(
            "No puedes incluir dos veces a la misma jugadora",
            "INVALID_MATCH_ROSTER",
            400
        )

    rows = MatchPlayer.query.filter_by(match_id=match.id).all()

    valid_player_ids = {
        row.player_id
        for row in rows
    }

    if not selected_ids.issubset(valid_player_ids):
        return error_response(
            "Uno o más participantes no pertenecen a este partido",
            "INVALID_MATCH_ROSTER",
            400
        )

    changed_rows = [
        row
        for row in rows
        if row.is_called != (row.player_id in selected_ids)
    ]

    if changed_rows and match.is_completed:
        return error_response(
            "El partido ya está finalizado y su estructura no puede modificarse.",
            "MATCH_COMPLETED",
            409
        )

    if match.is_completed and not changed_rows:
        return jsonify({
            "message": "Convocatoria guardada correctamente"
        }), 200

    removed_rows = [
        row
        for row in changed_rows
        if row.is_called and row.player_id not in selected_ids
    ]

    for row in removed_rows:
        if match_player_has_sports_history(row):
            return error_response(
                (
                    "Esta jugadora ya tiene historial registrado en el "
                    "partido y no puede retirarse de la convocatoria."
                ),
                "MATCH_HISTORY_LOCKED",
                409
            )

    removed_player_ids = {
        row.player_id for row in removed_rows
    }

    removed_player_charges = []

    if removed_player_ids:
        removed_player_charges = PlayerPayment.query.filter(
            PlayerPayment.club_id == user.club_id,
            PlayerPayment.player_id.in_(removed_player_ids),
            PlayerPayment.match_id == match.id,
            PlayerPayment.payment_type == "referee"
        ).all()

    locked_referee_charge = next(
        (
            charge
            for charge in removed_player_charges
            if charge.status == "paid" or charge.has_receipt_history
        ),
        None
    )

    if locked_referee_charge:
        return error_response(
            (
                "No puedes retirar una jugadora con cargos de arbitraje "
                "pagados o con recibo"
            ),
            "MATCH_ROSTER_FINANCIALLY_LOCKED",
            409
        )

    for charge in removed_player_charges:
        if charge.status in ["pending", "overdue"]:
            db.session.delete(charge)

    for row in rows:
        was_called = row.player_id in selected_ids
        row.is_called = was_called

        if not was_called:
            row.attendance_status = None
            row.did_play = False
            row.is_on_court = False
            row.position = None

    match.match_step = max(match.match_step, 1)

    db.session.commit()

    return jsonify({
        "message": "Convocatoria guardada correctamente"
    }), 200

@api.route(
    "/matches/<string:match_id>/referee-charges/preview",
    methods=["GET"]
)
@jwt_required()
def preview_match_referee_charges(match_id):
    user = get_current_user()

    match = (
        MatchSession.query
        .join(Team)
        .filter(
            MatchSession.id == match_id,
            Team.club_id == user.club_id
        )
        .first()
    )

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede consultar el reparto de arbitraje",
            "FORBIDDEN",
            403
        )

    if match.referee_fee is None:
        return error_response(
            "Este partido no tiene costo de arbitraje",
            "REFEREE_FEE_NOT_CONFIGURED",
            400
        )

    referee_fee = Decimal(str(match.referee_fee)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    if referee_fee <= 0:
        return error_response(
            "El costo de arbitraje debe ser mayor que cero",
            "INVALID_REFEREE_FEE",
            400
        )

    called_players = MatchPlayer.query.filter_by(
        match_id=match.id,
        is_called=True
    ).order_by(
        MatchPlayer.player_number.asc()
    ).all()

    if not called_players:
        return error_response(
            "Debes guardar una convocatoria antes de repartir el arbitraje",
            "MATCH_ROSTER_REQUIRED",
            400
        )

    distributed_amounts = split_money_exactly(
        referee_fee,
        len(called_players)
    )

    existing_charges = PlayerPayment.query.filter_by(
        club_id=user.club_id,
        match_id=match.id,
        payment_type="referee"
    ).all()

    existing_by_player = {
        charge.player_id: charge
        for charge in existing_charges
    }

    players_preview = []

    for index, match_player in enumerate(called_players):
        existing_charge = existing_by_player.get(
            match_player.player_id
        )

        players_preview.append({
            "match_player_id": match_player.id,
            "player_id": match_player.player_id,
            "player_number": match_player.player_number,
            "player": match_player.player.serialize(),
            "amount": float(distributed_amounts[index]),
            "existing_charge": (
                existing_charge.serialize()
                if existing_charge
                else None
            )
        })

    has_paid_charges = any(
        charge.status == "paid" or charge.has_receipt_history
        for charge in existing_charges
    )

    can_generate = not has_paid_charges

    return jsonify({
        "match": match.serialize(),
        "referee_fee": float(referee_fee),
        "currency_code": match.team.club.currency_code,
        "called_players_count": len(called_players),
        "existing_charges_count": len(existing_charges),
        "has_paid_charges": has_paid_charges,
        "can_generate": can_generate,
        "players": players_preview
    }), 200

@api.route(
    "/matches/<string:match_id>/referee-charges",
    methods=["POST"]
)
@jwt_required()
def generate_match_referee_charges(match_id):
    user = get_current_user()

    match = (
        MatchSession.query
        .join(Team)
        .filter(
            MatchSession.id == match_id,
            Team.club_id == user.club_id
        )
        .first()
    )

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede generar cargos de arbitraje",
            "FORBIDDEN",
            403
        )

    if match.referee_fee is None:
        return error_response(
            "Este partido no tiene costo de arbitraje",
            "REFEREE_FEE_NOT_CONFIGURED",
            400
        )

    referee_fee = Decimal(str(match.referee_fee)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    if referee_fee <= 0:
        return error_response(
            "El costo de arbitraje debe ser mayor que cero",
            "INVALID_REFEREE_FEE",
            400
        )

    called_players = MatchPlayer.query.filter_by(
        match_id=match.id,
        is_called=True
    ).order_by(
        MatchPlayer.player_number.asc()
    ).all()

    if not called_players:
        return error_response(
            "Debes guardar una convocatoria antes de generar los cargos",
            "MATCH_ROSTER_REQUIRED",
            400
        )

    existing_charges = PlayerPayment.query.filter_by(
        club_id=user.club_id,
        match_id=match.id,
        payment_type="referee"
    ).all()

    protected_charges = [
        charge
        for charge in existing_charges
        if charge.status == "paid" or charge.has_receipt_history
    ]

    if protected_charges:
        return error_response(
            (
                "No puedes recalcular el arbitraje porque uno o más "
                "cargos ya fueron pagados o tienen recibo"
            ),
            "REFEREE_CHARGES_LOCKED",
            409
        )
    # Los cargos pendientes anteriores se reemplazan por el nuevo reparto.
    for charge in existing_charges:
        if charge.status in ["pending", "overdue", "cancelled"]:
            db.session.delete(charge)

    db.session.flush()

    distributed_amounts = split_money_exactly(
        referee_fee,
        len(called_players)
    )

    created_charges = []

    tournament_team_id = match.tournament_team_id

    tournament_name = None

    if match.tournament_team:
        tournament_name = (
            match.tournament_team.tournament.name
            if match.tournament_team.tournament
            else None
        )

    for index, match_player in enumerate(called_players):
        notes_parts = [
            f"Arbitraje del partido contra {match.opponent_name}"
        ]

        if tournament_name:
            notes_parts.append(
                f"Torneo: {tournament_name}"
            )

        charge = PlayerPayment(
            club_id=user.club_id,
            player_id=match_player.player_id,
            tournament_team_id=tournament_team_id,
            match_id=match.id,
            payment_type="referee",
            amount=distributed_amounts[index],
            currency_code=match.team.club.currency_code,
            status="pending",
            due_date=match.date,
            notes=" · ".join(notes_parts),
            created_by=user.id
        )

        charge = add_charge_if_absent(
            charge=charge,
            identity_filters={
                "club_id": user.club_id,
                "player_id": match_player.player_id,
                "match_id": match.id,
                "payment_type": "referee"
            },
            constraint_name=(
                "uq_player_payments_referee_charge"
            )
        )

        created_charges.append(charge)

    db.session.commit()

    return jsonify({
        "message": "Cargos de arbitraje generados correctamente",
        "referee_fee": float(referee_fee),
        "currency_code": match.team.club.currency_code,
        "total_charges": len(created_charges),
        "charges": [
            charge.serialize()
            for charge in created_charges
        ]
    }), 201

@api.route("/matches/<string:match_id>/roster/status", methods=["PUT"])
@jwt_required()
def update_match_status(match_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response("Partido no encontrado", "MATCH_NOT_FOUND", 404)

    if match.team.club_id != user.club_id:
        return error_response("No tienes acceso", "FORBIDDEN", 403)

    sport_adapter = get_club_sport_adapter(match.team.club)

    body = request.get_json() or {}
    players = body.get("players")

    if not players:
        return error_response("Lista requerida", "MATCH_STATUS_REQUIRED", 400)

    planned_updates = []
    has_any_real_change = False

    for item in players:
        match_player_id = item.get("match_player_id")
        status = item.get("attendance_status")
        position_was_provided = "position" in item
        raw_position = item.get("position")

        if (
            position_was_provided
            and raw_position is not None
            and not isinstance(raw_position, str)
        ):
            return error_response(
                "Posición inválida",
                "INVALID_POSITION",
                400
            )

        position = (
            (raw_position or "").strip().lower()
            if position_was_provided
            else None
        )

        if not match_player_id:
            return error_response(
                "Registro del partido requerido",
                "MATCH_PLAYER_ID_REQUIRED",
                400
            )

        row = MatchPlayer.query.get(match_player_id)

        if not row:
            return error_response(
                "Registro del partido no encontrado",
                "MATCH_PLAYER_NOT_FOUND",
                404
            )

        if row.match_id != match.id:
            return error_response(
                "La jugadora no pertenece a este partido",
                "MATCH_PLAYER_INVALID",
                400
            )

        if not row.is_called:
            return error_response(
                "La jugadora no está convocada para este partido",
                "PLAYER_NOT_CALLED",
                400
            )

        if status not in VALID_MATCH_STATUSES:
            return error_response(
                "Estado inválido",
                "INVALID_MATCH_STATUS",
                400
            )

        target_did_play = row.did_play
        target_is_on_court = row.is_on_court

        if status in PLAYABLE_MATCH_STATUSES:
            if position and not sport_adapter.has_position(position):
                return error_response(
                    "Posición inválida",
                    "INVALID_POSITION",
                    400
                )

            target_position = (
                position
                if position_was_provided
                else row.position
            )
        else:
            target_position = None
            target_did_play = False
            target_is_on_court = False

        has_real_change = (
            row.attendance_status != status
            or row.position != target_position
            or row.did_play != target_did_play
            or row.is_on_court != target_is_on_court
        )
        has_any_real_change = (
            has_any_real_change or has_real_change
        )

        if has_real_change and match.is_completed:
            return error_response(
                "El partido ya está finalizado y su estructura no puede modificarse.",
                "MATCH_COMPLETED",
                409
            )

        if (
            has_real_change
            and status not in PLAYABLE_MATCH_STATUSES
            and match_player_has_sports_history(row)
        ):
            return error_response(
                (
                    "Esta jugadora ya tiene historial registrado en el "
                    "partido y su asistencia no puede cambiarse a ese estado."
                ),
                "MATCH_HISTORY_LOCKED",
                409
            )

        planned_updates.append((
            row,
            status,
            target_position,
            target_did_play,
            target_is_on_court
        ))

    if match.is_completed and not has_any_real_change:
        return jsonify({
            "message": "Estado del día actualizado"
        }), 200

    for (
        row,
        status,
        target_position,
        target_did_play,
        target_is_on_court
    ) in planned_updates:
        row.attendance_status = status
        row.position = target_position
        row.did_play = target_did_play
        row.is_on_court = target_is_on_court

    match.match_step = max(match.match_step, 2)

    db.session.commit()

    return jsonify({
        "message": "Estado del día actualizado"
    }), 200

@api.route("/matches", methods=["GET"])
@jwt_required()
def get_club_matches():
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver partidos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    matches = MatchSession.query.join(Team).filter(
        Team.club_id == user.club_id
    ).order_by(
        MatchSession.date.desc()
    ).all()

    result = []

    for match in matches:
        team = match.team
        category = team.category if team else None

        result.append({
            **match.serialize(),
            "team_id": team.id if team else None,
            "team_name": team.name if team else None,
            "category_id": category.id if category else None,
            "category_name": category.name if category else None,
        })

    return jsonify({
        "matches": result
    }), 200

@api.route("/matches/<string:match_id>", methods=["GET"])
@jwt_required()
def get_match_detail(match_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    return jsonify({
        "match": match.serialize()
    }), 200


@api.route("/matches/<string:match_id>/capture-mode", methods=["PUT"])
@jwt_required()
def update_match_capture_mode(match_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para configurar el modo de captura",
            "FORBIDDEN",
            403
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}
    capture_mode = body.get("capture_mode")

    if capture_mode not in VALID_MATCH_CAPTURE_MODES:
        return error_response(
            "Modo de captura inválido",
            "INVALID_MATCH_CAPTURE_MODE",
            400
        )

    if match.capture_mode == capture_mode:
        return jsonify({
            "message": "Modo de captura actualizado",
            "match": match.serialize()
        }), 200

    if match.is_completed:
        return error_response(
            "El modo de captura no puede cambiarse en un partido finalizado.",
            "MATCH_CAPTURE_MODE_LOCKED",
            409
        )

    if match_has_statistical_data(match.id):
        return error_response(
            (
                "El modo de captura no puede cambiarse porque el partido "
                "ya tiene información estadística."
            ),
            "MATCH_CAPTURE_MODE_LOCKED",
            409
        )

    match.capture_mode = capture_mode
    db.session.commit()

    return jsonify({
        "message": "Modo de captura actualizado",
        "match": match.serialize()
    }), 200

@api.route("/matches/<string:match_id>/roster", methods=["GET"])
@jwt_required()
def get_match_roster(match_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    synced_count = sync_match_roster_if_open(match)

    roster = MatchPlayer.query.filter_by(
        match_id=match.id
    ).order_by(MatchPlayer.player_number).all()

    players = []

    for row in roster:
        if not row.player:
            continue

        players.append({
            "match_player_id": row.id,
            "player_id": row.player.id,
            "first_name": row.player.first_name,
            "last_name": row.player.last_name,
            "player_number": row.player_number,
            "attendance_status": row.attendance_status,
            "did_play": row.did_play,
            "is_called": row.is_called,
            "is_on_court": row.is_on_court,
            "main_position": row.player.main_position,
            "position": row.position,
        })

    return jsonify({
        "players": players,
        "synced_count": synced_count
    }), 200

@api.route("/matches/<string:match_id>/starting-lineup", methods=["PUT"])
@jwt_required()
def save_starting_lineup(match_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    if match.is_completed:
        return error_response(
            "El partido ya está finalizado y su estructura no puede modificarse.",
            "MATCH_COMPLETED",
            409
        )

    lineup_size = _get_match_lineup_size(match)

    if lineup_size is None:
        return error_response(
            "El deporte del club no tiene una alineación válida configurada.",
            "MATCH_LINEUP_NOT_SUPPORTED",
            409
        )

    body = request.get_json() or {}
    players = body.get("players")

    if not players:
        return error_response(
            "Debes seleccionar las jugadoras iniciales",
            "STARTING_LINEUP_REQUIRED",
            400
        )

    if len(players) != lineup_size:
        return error_response(
            (
                "Debes seleccionar exactamente "
                f"{lineup_size} jugadoras en cancha"
            ),
            "STARTING_LINEUP_MUST_HAVE_6",
            400
        )

    selected_ids = set(players)

    rows = MatchPlayer.query.filter_by(match_id=match.id).all()

    valid_rows = []

    for row in rows:
        if row.id in selected_ids:
            valid_rows.append(row)

    if len(valid_rows) != lineup_size:
        return error_response(
            "Una o más jugadoras no pertenecen a este partido",
            "INVALID_STARTING_LINEUP",
            400
        )

    for row in valid_rows:
        if not row.is_called:
            return error_response(
                "Todas las jugadoras iniciales deben estar convocadas",
                "PLAYER_NOT_CALLED",
                400
            )

        if row.attendance_status not in PLAYABLE_MATCH_STATUSES:
            return error_response(
                "Todas las jugadoras iniciales deben estar presentes o tarde",
                "PLAYER_NOT_ELIGIBLE_FOR_LINEUP",
                400
            )

    has_real_change = any(
        row.is_on_court != (row.id in selected_ids)
        or (
            row.id in selected_ids
            and (
                not row.did_play
                or (
                    not row.position
                    and row.player.main_position is not None
                )
            )
        )
        for row in rows
    )

    if (
        has_real_change
        and match_has_recorded_game_history(match.id)
    ):
        return error_response(
            (
                "El partido ya tiene historial de juego y la alineación "
                "inicial no puede volver a establecerse."
            ),
            "MATCH_HISTORY_LOCKED",
            409
        )

    for row in rows:
        row.is_on_court = row.id in selected_ids

        if row.is_on_court:
            row.did_play = True
            row.position = row.position or row.player.main_position

    match.match_step = max(match.match_step, 3)

    db.session.commit()

    return jsonify({
        "message": "Alineación inicial guardada correctamente",
        "players": [row.serialize() for row in rows]
    }), 200

@api.route("/matches/<string:match_id>/substitutions", methods=["POST"])
@jwt_required()
def create_match_substitution(match_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    if match.is_completed:
        return error_response(
            "El partido ya está finalizado y no admite nuevas sustituciones.",
            "MATCH_COMPLETED",
            409
        )

    period_range = _get_match_period_range(match)

    if period_range is None:
        return error_response(
            "El deporte del club no tiene períodos válidos configurados.",
            "MATCH_PERIODS_NOT_SUPPORTED",
            409
        )

    period_min, period_max = period_range

    body = request.get_json() or {}

    player_out_id = body.get("player_out_id")
    player_in_id = body.get("player_in_id")

    try:
        set_number = int(body.get("set_number", period_min))
    except (TypeError, ValueError):
        return error_response(
            "Set inválido",
            "INVALID_SET_NUMBER",
            400
        )

    if set_number < period_min or set_number > period_max:
        return error_response(
            f"El set debe estar entre {period_min} y {period_max}",
            "INVALID_SET_NUMBER",
            400
        )

    if not player_out_id or not player_in_id:
        return error_response(
            "Debes indicar quién sale y quién entra",
            "SUBSTITUTION_PLAYERS_REQUIRED",
            400
        )

    if player_out_id == player_in_id:
        return error_response(
            "La jugadora que entra no puede ser la misma que sale",
            "INVALID_SUBSTITUTION",
            400
        )

    player_out = MatchPlayer.query.get(player_out_id)
    player_in = MatchPlayer.query.get(player_in_id)

    if not player_out or not player_in:
        return error_response(
            "Jugadora no encontrada en el partido",
            "MATCH_PLAYER_NOT_FOUND",
            404
        )

    if player_out.match_id != match.id or player_in.match_id != match.id:
        return error_response(
            "Las jugadoras no pertenecen a este partido",
            "MATCH_PLAYER_INVALID",
            400
        )

    if not player_out.is_called or not player_in.is_called:
        return error_response(
            "Ambas jugadoras deben estar convocadas",
            "PLAYER_NOT_CALLED",
            400
        )

    if player_out.attendance_status not in PLAYABLE_MATCH_STATUSES:
        return error_response(
            "La jugadora que sale no está disponible para jugar",
            "PLAYER_OUT_NOT_ELIGIBLE",
            400
        )

    if not player_out.is_on_court:
        return error_response(
            "La jugadora que sale debe estar en cancha",
            "PLAYER_OUT_NOT_ON_COURT",
            400
        )

    if player_in.is_on_court:
        return error_response(
            "La jugadora que entra ya está en cancha",
            "PLAYER_IN_ALREADY_ON_COURT",
            400
        )

    if not player_in.is_called:
        return error_response(
            "La jugadora que entra debe estar convocada",
            "PLAYER_NOT_CALLED",
            400
        )

    if player_in.attendance_status not in PLAYABLE_MATCH_STATUSES:
        return error_response(
            "La jugadora que entra debe estar presente o haber llegado tarde",
            "PLAYER_NOT_ELIGIBLE_FOR_SUBSTITUTION",
            400
        )

    substitution = MatchSubstitution(
        match_id=match.id,
        set_number=set_number,
        player_out_id=player_out.id,
        player_in_id=player_in.id
    )

    player_out.is_on_court = False
    player_in.is_on_court = True
    player_in.did_play = True

    match.match_step = max(match.match_step, 3)

    db.session.add(substitution)
    db.session.commit()

    return jsonify({
        "message": "Cambio registrado correctamente",
        "substitution": substitution.serialize()
    }), 201

@api.route("/matches/<string:match_id>/roster/participation", methods=["PUT"])
@jwt_required()
def update_match_participation(match_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    if match.capture_mode == "live":
        return error_response(
            "La participación de este partido se determina desde LiveMatch.",
            "MATCH_PARTICIPATION_MANAGED_BY_LIVE",
            409
        )

    if match.capture_mode is None:
        if match_has_statistical_data(match.id):
            return error_response(
                (
                    "Este partido tiene estadísticas históricas sin un modo "
                    "de captura verificable y no admite cambios de participación."
                ),
                "MATCH_CAPTURE_MODE_LEGACY_LOCKED",
                409
            )

        return error_response(
            "Elige cómo registrarás las estadísticas de este partido.",
            "MATCH_CAPTURE_MODE_REQUIRED",
            409
        )

    body = request.get_json() or {}
    players = body.get("players")

    if not isinstance(players, list) or not players:
        return error_response(
            "Lista requerida",
            "MATCH_PARTICIPATION_REQUIRED",
            400
        )

    planned_updates = []
    has_any_real_change = False
    seen_match_player_ids = set()

    for item in players:
        if not isinstance(item, dict):
            return error_response(
                "Lista de participación inválida",
                "INVALID_MATCH_PARTICIPATION",
                400
            )

        match_player_id = item.get("match_player_id")

        if not match_player_id:
            return error_response(
                "Registro del partido requerido",
                "MATCH_PLAYER_ID_REQUIRED",
                400
            )

        if match_player_id in seen_match_player_ids:
            return error_response(
                "La lista contiene jugadoras duplicadas",
                "DUPLICATE_MATCH_PARTICIPANT",
                400
            )

        seen_match_player_ids.add(match_player_id)

        if not isinstance(item.get("did_play"), bool):
            return error_response(
                "La participación debe ser verdadera o falsa",
                "INVALID_MATCH_PARTICIPATION",
                400
            )

        row = MatchPlayer.query.get(match_player_id)

        if not row:
            return error_response(
                "Registro del partido no encontrado",
                "MATCH_PLAYER_NOT_FOUND",
                404
            )

        if row.match_id != match.id:
            return error_response(
                "La jugadora no pertenece a este partido",
                "MATCH_PLAYER_INVALID",
                400
            )

        if not row.is_called:
            return error_response(
                "La jugadora no está convocada para este partido",
                "PLAYER_NOT_CALLED",
                400
            )

        did_play = item["did_play"]

        if (
            did_play
            and row.attendance_status not in PLAYABLE_MATCH_STATUSES
        ):
            return error_response(
                "La jugadora no puede marcar participación con ese estado",
                "PLAYER_NOT_ELIGIBLE_FOR_PARTICIPATION",
                400
            )

        has_real_change = row.did_play != did_play
        has_any_real_change = (
            has_any_real_change or has_real_change
        )

        if has_real_change and match.is_completed:
            return error_response(
                "El partido ya está finalizado y su estructura no puede modificarse.",
                "MATCH_COMPLETED",
                409
            )

        if (
            has_real_change
            and match_player_has_sports_history(row)
        ):
            return error_response(
                (
                    "Esta jugadora ya tiene historial registrado en el "
                    "partido y su participación no puede modificarse."
                ),
                "MATCH_HISTORY_LOCKED",
                409
            )

        planned_updates.append((
            row,
            did_play
        ))

    if match.is_completed and not has_any_real_change:
        return jsonify({
            "message": "Participación guardada"
        }), 200

    for row, did_play in planned_updates:
        row.did_play = did_play

    match.match_step = max(match.match_step, 3)

    db.session.commit()

    return jsonify({
        "message": "Participación guardada"
    }), 200

@api.route("/match-players/<string:match_player_id>/stats", methods=["POST"])
@jwt_required()
def save_match_stats(match_player_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    row = MatchPlayer.query.get(match_player_id)

    if not row:
        return error_response(
            "Registro del partido no encontrado",
            "MATCH_PLAYER_NOT_FOUND",
            404
        )

    if row.match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    if row.match.is_completed:
        return error_response(
            "El partido ya fue finalizado y no puede modificarse.",
            "MATCH_FINALIZED",
            409
        )

    mode_error = capture_mode_write_error(
        row.match,
        "summary"
    )

    if mode_error:
        return mode_error

    if (
        not row.is_called or
        row.attendance_status not in PLAYABLE_MATCH_STATUSES or
        not row.did_play
    ):
        return error_response(
            "La jugadora no puede registrar stats",
            "PLAYER_NOT_ELIGIBLE_FOR_STATS",
            400
        )

    body = request.get_json() or {}

    validated_stats, error = validate_match_stats(body)

    if error:
        return error_response(
            "Datos inválidos en estadísticas",
            error,
            400
        )

    stat = PlayerMatchStat.query.filter_by(
        match_player_id=row.id
    ).first()

    if not stat:
        stat = PlayerMatchStat(match_player_id=row.id)
        db.session.add(stat)

    stat.attacks_total = validated_stats.get("attacks_total")
    stat.attacks_positive = validated_stats.get("attacks_positive")
    stat.attacks_neutral = validated_stats.get("attacks_neutral")
    stat.attacks_errors = validated_stats.get("attacks_errors")

    stat.receptions_total = validated_stats.get("receptions_total")
    stat.receptions_positive = validated_stats.get("receptions_positive")
    stat.receptions_neutral = validated_stats.get("receptions_neutral")
    stat.receptions_negative = validated_stats.get("receptions_negative")

    stat.defenses_total = validated_stats.get("defenses_total")
    stat.defenses_positive = validated_stats.get("defenses_positive")
    stat.defenses_neutral = validated_stats.get("defenses_neutral")
    stat.defenses_negative = validated_stats.get("defenses_negative")

    stat.sets_total = validated_stats.get("sets_total")
    stat.sets_positive = validated_stats.get("sets_positive")
    stat.sets_neutral = validated_stats.get("sets_neutral")
    stat.sets_errors = validated_stats.get("sets_errors")

    stat.serves_total = validated_stats.get("serves_total")
    stat.serves_in = validated_stats.get("serves_in")
    stat.serves_aces = validated_stats.get("serves_aces")
    stat.serves_errors = validated_stats.get("serves_errors")

    stat.blocks_total = validated_stats.get("blocks_total")
    stat.blocks_points = validated_stats.get("blocks_points")
    stat.blocks_neutral = validated_stats.get("blocks_neutral")
    stat.blocks_errors = validated_stats.get("blocks_errors")


    row.match.match_step = max(row.match.match_step, 4)


    db.session.commit()

    return jsonify({
        "message": "Stats guardadas correctamente",
        "stats": stat.serialize()
    }), 200

@api.route("/match-players/<string:match_player_id>/stats", methods=["GET"])
@jwt_required()
def get_match_stats(match_player_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    row = MatchPlayer.query.get(match_player_id)

    if not row:
        return error_response(
            "Registro del partido no encontrado",
            "MATCH_PLAYER_NOT_FOUND",
            404
        )

    if row.match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    stats = PlayerMatchStat.query.filter_by(
        match_player_id=row.id
    ).first()

    team = row.match.team
    player = row.player
    match = row.match

    return jsonify({
        "context": {
            "player": {
                "id": player.id,
                "first_name": player.first_name,
                "last_name": player.last_name,
                "player_number": row.player_number,
                "sex": player.sex,
                "main_position": player.main_position,
            },
            "team": {
                "id": team.id,
                "name": team.name,
                "gender": team.gender
            },
            "match": {
                "id": match.id,
                "date": match.date.isoformat() if match.date else None,
                "opponent_name": match.opponent_name,
                "match_type": match.match_type,
                "location": match.location,
                "home_sets": match.home_sets,
                "opponent_sets": match.opponent_sets,
                "result": match.result,
                "is_completed": match.is_completed,
                "capture_mode": match.capture_mode
            },
            "match_player": {
                "id": row.id,
                "is_called": row.is_called,
                "attendance_status": row.attendance_status,
                "did_play": row.did_play,
                "position": row.position or player.main_position

            }
        },
        "stats": stats.serialize() if stats else None
    }), 200

@api.route("/matches/<string:match_id>/result", methods=["PUT"])
@jwt_required()
def update_match_result(match_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response("No tienes acceso", "FORBIDDEN", 403)

    if match.is_completed:
        return error_response(
            "El partido ya fue finalizado y su resultado no puede modificarse.",
            "MATCH_FINALIZED",
            409
        )

    body = request.get_json() or {}

    validated_result, validation_error = _validate_match_result(
        match,
        body.get("home_sets", 0),
        body.get("opponent_sets", 0)
    )

    if validated_result is None and validation_error is None:
        return error_response(
            "El deporte del club no tiene una validación de resultado configurada.",
            "MATCH_RESULT_NOT_SUPPORTED",
            409
        )

    if validation_error:
        return error_response(
            validation_error,
            "INVALID_MATCH_RESULT",
            400
        )

    match.home_sets = validated_result.home_value
    match.opponent_sets = validated_result.opponent_value
    match.result = validated_result.result

    db.session.commit()

    return jsonify({
        "message": "Resultado guardado",
        "match": match.serialize()
    }), 200


@api.route("/matches/<string:match_id>/finalize", methods=["PUT"])
@jwt_required()
def finalize_match(match_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para finalizar partidos",
            "FORBIDDEN",
            403
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    validated_result, validation_error = _validate_match_result(
        match,
        match.home_sets,
        match.opponent_sets
    )

    if validated_result is None and validation_error is None:
        return error_response(
            "El deporte del club no tiene una validación de resultado configurada.",
            "MATCH_RESULT_NOT_SUPPORTED",
            409
        )

    if validation_error or not match_has_valid_result(match, validated_result):
        return error_response(
            "Debes guardar un resultado válido antes de finalizar el partido.",
            "MATCH_RESULT_INCOMPLETE",
            409
        )

    if match.is_completed:
        return jsonify({
            "message": "Partido finalizado correctamente",
            "match": match.serialize()
        }), 200

    match.is_completed = True
    db.session.commit()

    return jsonify({
        "message": "Partido finalizado correctamente",
        "match": match.serialize()
    }), 200

############################################ MATCH EVENTS #############################################


@api.route("/match-events", methods=["POST"])
@jwt_required()
def create_match_event():
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    match_id = body.get("match_id")
    match_player_id = body.get("match_player_id")
    action = body.get("action_type")
    result = body.get("result")
    set_number_was_provided = "set_number" in body
    set_number = None

    if set_number_was_provided:
        try:
            set_number = int(body.get("set_number"))
        except (TypeError, ValueError):
            return error_response(
                "Set inválido",
                "INVALID_SET_NUMBER",
                400
            )

    if not match_id or not match_player_id:
        return error_response(
            "Datos incompletos",
            "MATCH_EVENT_REQUIRED",
            400
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    if match.is_completed:
        return error_response(
            "El partido ya está finalizado y no admite nuevos eventos.",
            "MATCH_COMPLETED",
            409
        )

    event_validation = _validate_match_event(match, action, result)

    if event_validation is None:
        return error_response(
            "El deporte del club no tiene eventos válidos configurados.",
            "MATCH_EVENT_RULES_NOT_SUPPORTED",
            409
        )

    event_exists, result_allowed = event_validation

    if not event_exists:
        return error_response(
            "Acción inválida",
            "INVALID_EVENT_ACTION",
            400
        )

    if not result_allowed:
        return error_response(
            "Resultado inválido para esta acción",
            "INVALID_EVENT_RESULT",
            400
        )

    period_range = _get_match_period_range(match)

    if period_range is None:
        return error_response(
            "El deporte del club no tiene períodos válidos configurados.",
            "MATCH_PERIODS_NOT_SUPPORTED",
            409
        )

    period_min, period_max = period_range

    if not set_number_was_provided:
        set_number = period_min

    if set_number < period_min or set_number > period_max:
        return error_response(
            f"El set debe estar entre {period_min} y {period_max}",
            "INVALID_SET_NUMBER",
            400
        )

    mode_error = capture_mode_write_error(match, "live")

    if mode_error:
        return mode_error

    # 🔒 Validar que el match_player pertenece a ese match
    match_player = MatchPlayer.query.get(match_player_id)

    if not match_player or match_player.match_id != match.id:
        return error_response(
            "Registro inválido",
            "MATCH_PLAYER_INVALID",
            400
        )

    if (
        not match_player.is_called or
        match_player.attendance_status not in PLAYABLE_MATCH_STATUSES or
        not match_player.is_on_court
    ):
        return error_response(
            "Solo puedes registrar acciones a jugadoras en cancha",
            "PLAYER_NOT_ON_COURT",
            400
        )

    match_player.did_play = True
    match_player.position = match_player.position or match_player.player.main_position

    event = MatchEvent(
        match_id=match_id,
        match_player_id=match_player_id,
        action_type=action,
        result=result,
        set_number=set_number
    )

    db.session.add(event)
    db.session.flush()

    recalculate_player_match_stats(match_player_id)

    db.session.commit()

    return jsonify({
        "message": "Evento registrado correctamente",
        "event": event.serialize()
    }), 201

@api.route("/match-events/<string:event_id>", methods=["DELETE"])
@jwt_required()
def delete_match_event(event_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para acceder a partidos",
            "FORBIDDEN",
            403
        )

    event = MatchEvent.query.get(event_id)

    if not event:
        return error_response(
            "Evento no encontrado",
            "MATCH_EVENT_NOT_FOUND",
            404
        )

    match = MatchSession.query.get(event.match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    if match.is_completed:
        return error_response(
            "El partido ya fue finalizado y no puede modificarse.",
            "MATCH_FINALIZED",
            409
        )

    mode_error = capture_mode_write_error(match, "live")

    if mode_error:
        return mode_error

    match_player_id = event.match_player_id

    db.session.delete(event)
    db.session.flush()

    recalculate_player_match_stats(match_player_id)

    db.session.commit()

    return jsonify({
        "message": "Evento eliminado correctamente"
    }), 200
