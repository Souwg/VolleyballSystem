import os
import uuid
from datetime import datetime

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from src.api.api_blueprint import api
from src.api.models import (
    db,
    Attendance,
    MatchPlayer,
    PaymentReceipt,
    Player,
    PlayerPayment,
    Team,
    TeamPlayer,
    TournamentPlayer,
    TrainingPlayer,
)
from src.api.upload_utils import allowed_image_file
from src.api.onboarding_service import is_club_onboarding_complete
from src.api.season_service import (
    get_team_membership_operation_error,
    resolve_season_for_read,
)
from src.api.sports import get_club_sport_adapter
from src.api.utils import error_response, get_current_user


MAX_PLAYER_IMAGE_SIZE = 8 * 1024 * 1024
MAX_PLAYER_IMAGE_SIZE_MB = MAX_PLAYER_IMAGE_SIZE // (1024 * 1024)


def ensure_planned_roster_owner(user, team):
    if team.season and team.season.status == "planned" and user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede preparar el roster de otra temporada",
            "FORBIDDEN",
            403,
        )

    return None


def ensure_player_creation_allowed_during_setup(user):
    if user.role != "coach":
        return None

    club = user.club

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    if not is_club_onboarding_complete(club):
        return error_response(
            (
                "El club todavía está siendo configurado. "
                "El dueño debe completar la configuración inicial."
            ),
            "CLUB_SETUP_PENDING",
            403
        )

    return None


@api.route("/teams/<string:team_id>/players/<string:player_id>", methods=["DELETE"])
@jwt_required()
def remove_player_from_team(team_id, player_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response("No tienes permisos", "FORBIDDEN", 403)

    team = Team.query.get(team_id)

    if not team or team.club_id != user.club_id:
        return error_response("Equipo no encontrado", "TEAM_NOT_FOUND", 404)

    team_error = get_team_membership_operation_error(team)
    if team_error:
        return error_response(*team_error)

    role_error = ensure_planned_roster_owner(user, team)
    if role_error:
        return role_error

    membership = TeamPlayer.query.filter_by(
        team_id=team.id,
        player_id=player_id,
        left_at=None
    ).with_for_update().first()

    if not membership:
        return error_response(
            "El jugador no pertenece a este equipo",
            "PLAYER_MEMBERSHIP_NOT_FOUND",
            404
        )

    membership.left_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "message": "Jugador removido del equipo"
    }), 200


@api.route("/players", methods=["POST"])
@jwt_required()
def create_player():

    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "Solo el dueño del club o un entrenador pueden registrar jugadores",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    setup_error = ensure_player_creation_allowed_during_setup(user)

    if setup_error:
        return setup_error

    body = request.get_json() or {}

    first_name = body.get("first_name")
    last_name = body.get("last_name")
    player_number = body.get("player_number")
    sex = body.get("sex")
    birth_date = body.get("birth_date")
    status = body.get("status", "active")
    team_id = body.get("team_id")
    representative_name = body.get("representative_name")
    representative_phone = body.get("representative_phone")

    if representative_name:
        representative_name = " ".join(str(representative_name).strip().split())

    if representative_phone:
        representative_phone = str(representative_phone).strip()

    sport_adapter = get_club_sport_adapter(user.club)
    main_position = (body.get("main_position") or "").strip().lower() or None

    if main_position and not sport_adapter.has_position(main_position):
        return error_response(
            "Posición inválida",
            "INVALID_POSITION",
            400
        )

    allowed_sex = ["male", "female"]

    if not sex:
        return error_response(
            "El sexo es obligatorio",
            "SEX_REQUIRED",
            400
        )

    if sex not in allowed_sex:
        return error_response(
            "Sexo inválido",
            "INVALID_SEX",
            400
        )

    allowed_status = ["active", "injured", "inactive"]

    if status not in allowed_status:
        return error_response(
            "Estado del jugador inválido",
            "INVALID_PLAYER_STATUS",
            400
        )

    if not first_name:
        return error_response(
            "Nombre del jugador requerido",
            "FIRST_NAME_REQUIRED",
            400
        )

    if not last_name:
        return error_response(
            "Apellido del jugador requerido",
            "LAST_NAME_REQUIRED",
            400
        )

    team = None

    if team_id:
        if player_number is None:
            return error_response(
                "El número del jugador es obligatorio",
                "PLAYER_NUMBER_REQUIRED",
                400
            )

        try:
            player_number = int(player_number)
        except (TypeError, ValueError):
            return error_response(
                "El número del jugador debe ser numérico",
                "INVALID_PLAYER_NUMBER",
                400
            )

        if player_number <= 0:
            return error_response(
                "El número del jugador debe ser mayor que cero",
                "INVALID_PLAYER_NUMBER",
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
                "No tienes permisos para registrar jugadores en este equipo",
                "FORBIDDEN",
                403
            )

        team_error = get_team_membership_operation_error(team)

        if team_error:
            return error_response(*team_error)

        role_error = ensure_planned_roster_owner(user, team)
        if role_error:
            return role_error

        if team.gender != "mixed" and team.gender != sex:
            return error_response(
                "El sexo del jugador no coincide con la rama del equipo",
                "PLAYER_GENDER_MISMATCH",
                400
            )

        existing_membership = TeamPlayer.query.filter_by(
            team_id=team.id,
            player_number=player_number,
            left_at=None
        ).first()

        if existing_membership:
            return error_response(
                "Ya existe un jugador con ese número en este equipo",
                "PLAYER_NUMBER_DUPLICATED",
                409
            )

    parsed_birth_date = None

    if birth_date:
        try:
            parsed_birth_date = datetime.strptime(
                birth_date, "%Y-%m-%d"
            ).date()
        except ValueError:
            return error_response(
                "Formato de fecha inválido. Usa YYYY-MM-DD",
                "INVALID_DATE_FORMAT",
                400
            )

    player = Player(
        first_name=first_name,
        last_name=last_name,
        sex=sex,
        birth_date=parsed_birth_date,
        main_position=main_position,
        representative_name=representative_name or None,
        representative_phone=representative_phone or None,
        club_id=user.club_id
    )

    db.session.add(player)
    db.session.flush()

    membership = None

    if team:
        membership = TeamPlayer(
            team_id=team.id,
            player_id=player.id,
            player_number=player_number,
            status=status
        )
        db.session.add(membership)
    db.session.commit()

    return jsonify({
        "message": "Jugador registrado correctamente",
        "player": {
            **player.serialize(),
            "team_id": membership.team_id if membership else None,
            "player_number": membership.player_number if membership else None,
            "status": membership.status if membership else "active"
        }
    }), 201


@api.route("/players/<string:player_id>/upload-image", methods=["POST"])
@jwt_required()
def upload_player_image(player_id):

    user = get_current_user()

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para modificar jugadores",
            "FORBIDDEN",
            403
        )

    if "image" not in request.files:
        return error_response(
            "Debes seleccionar una imagen",
            "IMAGE_REQUIRED",
            400
        )

    image = request.files["image"]

    if image.filename == "":
        return error_response(
            "Debes seleccionar una imagen",
            "IMAGE_REQUIRED",
            400
        )

    if not allowed_image_file(image.filename):
        return error_response(
            "Formato inválido. Usa PNG, JPG o WEBP",
            "INVALID_IMAGE_FORMAT",
            400
        )

    image.seek(0, os.SEEK_END)
    image_size = image.tell()
    image.seek(0)

    if image_size > MAX_PLAYER_IMAGE_SIZE:
        return error_response(
            (
                "La imagen no puede pesar más de "
                f"{MAX_PLAYER_IMAGE_SIZE_MB} MB"
            ),
            "IMAGE_TOO_LARGE",
            400
        )

    original_filename = secure_filename(image.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    filename = f"{player.id}-{uuid.uuid4().hex}.{extension}"

    upload_folder = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../../../public/uploads/players"
        )
    )

    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, filename)
    image.save(file_path)

    image_url = f"/uploads/players/{filename}"

    player.image_url = image_url
    db.session.commit()

    return jsonify({
        "image_url": image_url,
        "player": player.serialize()
    }), 201


@api.route("/players/<string:player_id>/active", methods=["PUT"])
@jwt_required()
def update_player_active_status(player_id):
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede cambiar el estado global de una jugadora",
            "FORBIDDEN",
            403
        )

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    body = request.get_json() or {}
    is_active = body.get("is_active")

    if not isinstance(is_active, bool):
        return error_response(
            "Estado inválido",
            "INVALID_PLAYER_ACTIVE_STATUS",
            400
        )

    player.is_active = is_active

    db.session.commit()

    return jsonify({
        "message": "Estado del jugador actualizado correctamente",
        "player": player.serialize()
    }), 200


@api.route("/teams/<string:team_id>/players", methods=["GET"])
@jwt_required()
def get_team_players(team_id):
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver jugadores",
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

    memberships = TeamPlayer.query.filter_by(team_id=team.id, left_at=None)\
        .order_by(TeamPlayer.player_number)\
        .all()

    players = [
        {
            "id": m.player.id,
            "first_name": m.player.first_name,
            "last_name": m.player.last_name,
            "sex": m.player.sex,
            "birth_date": m.player.birth_date.isoformat() if m.player.birth_date else None,
            "main_position": m.player.main_position,
            "team_id": m.team_id,
            "player_number": m.player_number,
            "status": m.status
        }
        for m in memberships
    ]

    return jsonify({
        "team": team.serialize(),
        "total_players": len(players),
        "players": players
    }), 200


@api.route("/players", methods=["GET"])
@jwt_required()
def get_players():
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para ver jugadores",
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

    players = Player.query.filter_by(
        club_id=user.club_id
    ).order_by(Player.created_at.desc()).all()

    serialized_players = []

    for player in players:
        memberships = sorted(
            (
                membership
                for membership in player.team_memberships
                if (
                    membership.team.club_id == user.club_id
                    and (
                        membership.team.season_id == season.id
                        if season
                        else membership.left_at is None
                    )
                )
            ),
            key=lambda membership: (
                membership.joined_at,
                membership.created_at or membership.joined_at,
                membership.id
            )
        )
        membership = memberships[0] if memberships else None

        serialized_players.append({
            **player.serialize(),
            "team_id": membership.team_id if membership else None,
            "player_number": membership.player_number if membership else None,
            "status": membership.status if membership else "active",
            "teams": [
                {
                    "id": m.team.id,
                    "name": m.team.name,
                    "gender": m.team.gender,
                    "category_id": m.team.category_id,
                    "category_name": m.team.category.name if m.team.category else None,
                    "player_number": m.player_number,
                    "status": m.status,
                    "membership_id": m.id,
                    "joined_at": m.joined_at.isoformat(),
                    "left_at": m.left_at.isoformat() if m.left_at else None,
                    "season_id": m.team.season_id,
                    "team_status": m.team.status,
                }
                for m in memberships
            ]
        })

    return jsonify({
        "season": season.serialize() if season else None,
        "total_players": len(serialized_players),
        "players": serialized_players
    }), 200


@api.route("/teams/<string:team_id>/players/existing", methods=["POST"])
@jwt_required()
def add_existing_player_to_team(team_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos",
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
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    team_error = get_team_membership_operation_error(team)

    if team_error:
        return error_response(*team_error)

    role_error = ensure_planned_roster_owner(user, team)
    if role_error:
        return role_error

    setup_error = ensure_player_creation_allowed_during_setup(user)

    if setup_error:
        return setup_error

    body = request.get_json() or {}

    player_id = body.get("player_id")
    player_number = body.get("player_number")

    if not player_id:
        return error_response(
            "Jugador requerido",
            "PLAYER_REQUIRED",
            400
        )

    if player_number is None:
        return error_response(
            "Número requerido",
            "PLAYER_NUMBER_REQUIRED",
            400
        )

    try:
        player_number = int(player_number)
    except (TypeError, ValueError):
        return error_response(
            "El número del jugador debe ser numérico",
            "INVALID_PLAYER_NUMBER",
            400
        )

    if player_number < 1 or player_number > 99:
        return error_response(
            "El número del jugador debe estar entre 1 y 99",
            "INVALID_PLAYER_NUMBER",
            400
        )

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    if not player.is_active:
        return error_response(
            "No puedes asignar una jugadora desactivada",
            "PLAYER_INACTIVE",
            400
        )

    if team.gender != "mixed" and team.gender != player.sex:
        return error_response(
            "El jugador no coincide con la rama de la categoría",
            "PLAYER_GENDER_MISMATCH",
            400
        )

    existing = TeamPlayer.query.filter_by(
        team_id=team.id,
        player_id=player.id,
        left_at=None
    ).first()

    if existing:
        return error_response(
            "El jugador ya pertenece al equipo",
            "PLAYER_ALREADY_IN_TEAM",
            409
        )

    duplicated_number = TeamPlayer.query.filter_by(
        team_id=team.id,
        player_number=player_number,
        left_at=None
    ).first()

    if duplicated_number:
        return error_response(
            "Número duplicado",
            "PLAYER_NUMBER_DUPLICATED",
            409
        )

    membership = TeamPlayer(
        team_id=team.id,
        player_id=player.id,
        player_number=player_number,
        status="active"
    )

    db.session.add(membership)
    db.session.commit()

    return jsonify({
        "message": "Jugador agregado al equipo",
        "player": membership.serialize()
    }), 201


@api.route("/players/<string:player_id>", methods=["PUT"])
@jwt_required()
def update_player(player_id):
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para modificar jugadores",
            "FORBIDDEN",
            403
        )

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    body = request.get_json() or {}

    first_name = body.get("first_name")
    last_name = body.get("last_name")
    sex = body.get("sex")
    birth_date = body.get("birth_date")
    team_id = body.get("team_id")
    representative_name = body.get("representative_name")
    representative_phone = body.get("representative_phone")

    sport_adapter = get_club_sport_adapter(player.club)
    main_position = (body.get("main_position") or "").strip().lower() or None

    if main_position and not sport_adapter.has_position(main_position):
        return error_response(
            "Posición inválida",
            "INVALID_POSITION",
            400
        )

    player_number = body.get("player_number")

    if not first_name:
        return error_response(
            "Nombre del jugador requerido",
            "FIRST_NAME_REQUIRED",
            400
        )

    if not last_name:
        return error_response(
            "Apellido del jugador requerido",
            "LAST_NAME_REQUIRED",
            400
        )

    allowed_sex = ["male", "female"]

    if sex not in allowed_sex:
        return error_response(
            "Sexo inválido",
            "INVALID_SEX",
            400
        )

    # ✅ validar cambio global de sexo contra TODAS sus categorías
    memberships = TeamPlayer.query.filter_by(
        player_id=player.id,
        left_at=None
    ).all()

    for membership in memberships:
        team = Team.query.get(membership.team_id)

        if not team:
            continue

        if team.gender != "mixed" and team.gender != sex:
            return error_response(
                "No puedes cambiar el sexo porque la jugadora pertenece a categorías incompatibles",
                "PLAYER_GENDER_MISMATCH",
                409
            )

    # ✅ actualizar perfil global
    player.first_name = first_name
    player.last_name = last_name
    player.sex = sex

    if representative_name is not None:
        representative_name = " ".join(str(representative_name).strip().split())
        player.representative_name = representative_name or None

    if representative_phone is not None:
        representative_phone = str(representative_phone).strip()
        player.representative_phone = representative_phone or None

    # ✅ fecha opcional
    if birth_date:
        try:
            player.birth_date = datetime.strptime(
                birth_date, "%Y-%m-%d"
            ).date()
        except ValueError:
            return error_response(
                "Formato de fecha inválido",
                "INVALID_DATE_FORMAT",
                400
            )

    # ✅ actualizar número SOLO en membership específica
    if team_id and player_number is not None:
        team = db.session.get(Team, team_id)

        if not team or team.club_id != user.club_id:
            return error_response("Equipo no encontrado", "TEAM_NOT_FOUND", 404)

        team_error = get_team_membership_operation_error(team)
        if team_error:
            return error_response(*team_error)

        role_error = ensure_planned_roster_owner(user, team)
        if role_error:
            return role_error

        membership = TeamPlayer.query.filter_by(
            player_id=player.id,
            team_id=team_id,
            left_at=None
        ).first()

        if not membership:
            return error_response(
                "El jugador no pertenece a esta categoría",
                "PLAYER_MEMBERSHIP_NOT_FOUND",
                404
            )

        try:
            player_number = int(player_number)
        except (TypeError, ValueError):
            return error_response(
                "El número del jugador debe ser numérico",
                "INVALID_PLAYER_NUMBER",
                400
            )

        if player_number < 1 or player_number > 99:
            return error_response(
                "El número del jugador debe estar entre 1 y 99",
                "INVALID_PLAYER_NUMBER",
                400
            )

        duplicated_number = TeamPlayer.query.filter(
            TeamPlayer.team_id == team_id,
            TeamPlayer.player_number == player_number,
            TeamPlayer.player_id != player.id,
            TeamPlayer.left_at.is_(None)
        ).first()

        if duplicated_number:
            return error_response(
                "Ya existe un jugador con ese número",
                "PLAYER_NUMBER_DUPLICATED",
                409
            )

        membership.player_number = int(player_number)

    player.main_position = main_position

    db.session.commit()

    return jsonify({
        "message": "Jugador actualizado correctamente",
        "player": player.serialize()
    }), 200


@api.route("/players/<string:player_id>/status", methods=["PUT"])
@jwt_required()
def update_player_status(player_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para modificar jugadores",
            "FORBIDDEN",
            403
        )

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    body = request.get_json() or {}
    status = body.get("status")
    team_id = body.get("team_id")

    if not team_id:
        return error_response(
            "La categoría es obligatoria",
            "TEAM_ID_REQUIRED",
            400
        )

    allowed_status = ["active", "injured", "inactive"]

    if status not in allowed_status:
        return error_response(
            "Estado del jugador inválido",
            "INVALID_PLAYER_STATUS",
            400
        )

    membership = TeamPlayer.query.filter_by(
        player_id=player.id,
        team_id=team_id,
        left_at=None
    ).first()

    if not membership:
        return error_response(
            "El jugador no pertenece a esta categoría",
            "PLAYER_MEMBERSHIP_NOT_FOUND",
            404
        )

    team = Team.query.get(team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "No tienes permisos para modificar este jugador",
            "FORBIDDEN",
            403
        )

    team_error = get_team_membership_operation_error(team)
    if team_error:
        return error_response(*team_error)

    role_error = ensure_planned_roster_owner(user, team)
    if role_error:
        return role_error

    membership.status = status
    db.session.commit()

    return jsonify({
        "message": "Estado del jugador actualizado correctamente",
        "player": {
            **player.serialize(),
            "team_id": membership.team_id,
            "player_number": membership.player_number,
            "status": membership.status
        }
    }), 200


@api.route("/players/<string:player_id>", methods=["DELETE"])
@jwt_required()
def delete_player(player_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede eliminar jugadoras del club",
            "FORBIDDEN",
            403
        )

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    memberships = TeamPlayer.query.filter_by(
        player_id=player.id
    ).all()

    has_history = (
        Attendance.query.filter_by(player_id=player.id).first() is not None
        or TrainingPlayer.query.filter_by(player_id=player.id).first() is not None
        or TournamentPlayer.query.filter_by(player_id=player.id).first() is not None
        or MatchPlayer.query.filter_by(player_id=player.id).first() is not None
        or PlayerPayment.query.filter_by(player_id=player.id).first() is not None
        or PaymentReceipt.query.filter_by(player_id=player.id).first() is not None
    )

    if has_history:
        return error_response(
            "No puedes eliminar una jugadora con historial registrado",
            "PLAYER_HAS_HISTORY",
            409
        )

    try:
        for membership in memberships:
            db.session.delete(membership)

        db.session.delete(player)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response(
            "No puedes eliminar una jugadora con historial registrado",
            "PLAYER_HAS_HISTORY",
            409
        )

    return jsonify({
        "message": "Jugador eliminado correctamente"
    }), 200
