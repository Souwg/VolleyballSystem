"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
from flask import Flask, request, jsonify, url_for, Blueprint
from sqlalchemy import func
from src.api.models import (
    db,
    User,
    Club,
    Player,
    Team,
    TeamPlayer,
    Attendance,
    TrainingSession,
    TrainingPlayer,
    TokenBlockedList,
    MatchSession,
    MatchPlayer,
    MatchSubstitution,
    MatchEvent,
    PlayerMatchStat,
    RefreshToken
)
from src.api.stats_validator import validate_match_stats
from flask_cors import CORS
from src.api.extensions import bcrypt
from src.api.utils import (
    generate_sitemap,
    APIException,
    get_current_user,
    error_response,
    generate_temp_password
)
from datetime import datetime, timedelta
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    decode_token
)

api = Blueprint('api', __name__)


CORS(api)

VALID_MATCH_STATUSES = ["present", "late", "absent", "injured"]
PLAYABLE_MATCH_STATUSES = ["present", "late"]
VALID_MATCH_STEPS = [0, 1, 2, 3, 4]
VALID_MATCH_TYPES = ["official", "friendly", "scrimmage"]
ALLOWED_POSITIONS = ["setter", "outside", "middle", "opposite", "libero"]

def sync_match_roster_if_open(match):
    """
    Sincroniza jugadoras nuevas del equipo al partido SOLO si el partido
    todavía no tiene convocatoria guardada.

    No elimina jugadoras viejas del snapshot.
    Solo agrega las que faltan.
    """

    if not match:
        return 0

    # Si ya avanzó de convocatoria, no tocamos el snapshot
    if match.match_step != 0:
        return 0

    if match.is_completed:
        return 0

    existing_player_ids = {
        row.player_id
        for row in MatchPlayer.query.filter_by(match_id=match.id).all()
    }

    current_roster = TeamPlayer.query.filter_by(
        team_id=match.team_id
    ).all()

    added_count = 0

    for member in current_roster:
        if member.player_id in existing_player_ids:
            continue

        snapshot = MatchPlayer(
            match_id=match.id,
            player_id=member.player_id,
            player_number=member.player_number,
            is_called=False,
            attendance_status=None,
            did_play=False
        )

        db.session.add(snapshot)
        added_count += 1

    if added_count > 0:
        db.session.commit()

    return added_count

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


######################### SYSTEM ###############################

@api.route('/hello', methods=['POST', 'GET'])
def handle_hello():

    response_body = {
        "message": "Hello Sousan! I'm a message that came from the backend, check the network tab on the google inspector and you will see the GET requestttttt"
    }

    return jsonify(response_body), 200

############################# AUTHENTICATION ##################################

@api.route('/login', methods=['POST'])
def login():
    body = request.get_json() or {}

    email = body.get("email")
    password = body.get("password")

    if not email:
        return error_response(
            "Email es obligatorio",
            "EMAIL_REQUIRED",
            400
        )

    if not password:
        return error_response(
            "Contraseña es obligatoria",
            "PASSWORD_REQUIRED",
            400
        )

    user = User.query.filter_by(email=email).first()

    if not user:
        return error_response(
            "Email o contraseña incorrectos",
            "INVALID_CREDENTIALS",
            401
        )
    
    if not user.is_active:
        return error_response(
            "Tu cuenta está desactivada. Contacta al administrador.",
            "ACCOUNT_DISABLED",
            403
        )
    if not bcrypt.check_password_hash(user.password, password):
        return error_response(
            "Email o contraseña incorrectos",
            "INVALID_CREDENTIALS",
            401
        )

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    decoded_refresh = decode_token(refresh_token)
    refresh_jti = decoded_refresh["jti"]

    refresh_entry = RefreshToken(
        user_id=user.id,
        jti=refresh_jti,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )

    db.session.add(refresh_entry)
    db.session.commit()

    return jsonify({
        "message": "Login exitoso",
        "token": access_token,
        "refresh": refresh_token,
        "first_login": user.first_login,
        "user": user.serialize()
    }), 200

@api.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():

    jwt_data = get_jwt()
    user_id = get_jwt_identity()
    jti = jwt_data["jti"]

    stored_token = RefreshToken.query.filter_by(jti=jti).first()

    
    if not stored_token:
        return error_response(
            "La sesión ya no es válida. Inicia sesión nuevamente",
            "REFRESH_NOT_FOUND",
            401
        )

    if stored_token.revoked:
        return error_response(
            "La sesión fue cerrada previamente",
            "REFRESH_REVOKED",
            401
        )

   
    stored_token.revoked = True

  
    new_access = create_access_token(identity=user_id)
    new_refresh = create_refresh_token(identity=user_id)

    decoded_new = decode_token(new_refresh)

    new_entry = RefreshToken(
        user_id=user_id,
        jti=decoded_new["jti"],
        expires_at=datetime.utcnow() + timedelta(days=7)
    )

    db.session.add(new_entry)
    db.session.commit()

    return jsonify({
        "token": new_access,
        "refresh": new_refresh
    }), 200

@api.route('/auth/set-password', methods=['POST'])
@jwt_required()
def set_password():

    user = get_current_user()

    body = request.get_json() or {}

    new_password = body.get("new_password")

    if not new_password:
        return error_response(
            "Nueva contraseña requerida",
            "PASSWORD_REQUIRED",
            400
        )

    if len(new_password) < 8:
        return error_response(
            "Debe tener al menos 8 caracteres",
            "PASSWORD_TOO_SHORT",
            400
        )

    user.password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    user.first_login = False  

    db.session.commit()

    return jsonify({
        "message": "Contraseña actualizada correctamente"
    }), 200

@api.route("/logout", methods=["POST"])
@jwt_required()
def logout():

    jwt_data = get_jwt()
    jti = jwt_data["jti"]

    blocked_token = TokenBlockedList(jti=jti)
    db.session.add(blocked_token)

    user = get_current_user()

    RefreshToken.query.filter_by(user_id=user.id, revoked=False).update({
        "revoked": True
    })

    db.session.commit()

    return jsonify({"message": "Logout exitoso"}), 200


######################################### ADMIN ############################################################
@api.route('/admin/create-client', methods=['POST'])
@jwt_required()
def create_client():

    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para crear clientes",
            "FORBIDDEN",
            403
        )
    
    body = request.get_json() or {}

    full_name = body.get("full_name")
    email = body.get("email")
    if email:
        email = email.strip().lower()
    club_name = body.get("club_name")

    if not full_name or not str(full_name).strip():
        return error_response(
            "Nombre completo es obligatorio",
            "FULL_NAME_REQUIRED",
            400
        )
    if not email:
        return error_response("email es obligatorio", "EMAIL_REQUIRED", 400)
    
    if not club_name or not str(club_name).strip():
        return error_response(
            "Nombre del club es obligatorio",
            "CLUB_NAME_REQUIRED",
            400
        )
    
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return error_response(
            "Ya existe un cliente con ese email",
            "CLIENT_ALREADY_EXISTS",
            409
        )


    temp_password = generate_temp_password(10)
    hashed_password = bcrypt.generate_password_hash(temp_password).decode("utf-8")

    new_user = User(
        full_name=full_name,
        email=email,
        password=hashed_password,
        first_login=True,
        role="club_owner"
    )

    db.session.add(new_user)
    db.session.flush()

    club = Club(
        name=club_name,
        location=None,
        owner_id=new_user.id
    )

    db.session.add(club)
    db.session.flush()

    new_user.club_id = club.id

    db.session.commit()

    return jsonify({
    "message": "Cliente creado exitosamente",
    "credentials": {
        "email": email,
        "temporary_password": temp_password
    },
    "user": new_user.serialize()
}), 201

@api.route('/admin/clients', methods=['GET'])
@jwt_required()
def list_clients():

    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para acceder a esta información",
            "FORBIDDEN",
            403
        )

    clients = User.query.filter_by(role="club_owner") \
        .order_by(User.created_at.desc()) \
        .all()

    return jsonify({
        "total": len(clients),
        "clients": [c.serialize() for c in clients]
    }), 200

@api.route('/admin/clients/<string:user_id>/deactivate', methods=['PUT'])
@jwt_required()
def deactivate_client(user_id):

    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para gestionar clientes",
            "FORBIDDEN",
            403
        )

    client = User.query.get(user_id)

    if not client:
        return error_response(
            "El cliente solicitado no existe",
            "CLIENT_NOT_FOUND",
            404
        )

    if client.role != "club_owner":
        return error_response(
            "Solo los clientes pueden ser desactivados",
            "INVALID_CLIENT",
            400
        )

    client.is_active = False
    db.session.commit()

    return jsonify({
        "message": "Cliente desactivado correctamente",
        "client": client.serialize()
    }), 200

@api.route('/admin/clients/<string:user_id>/activate', methods=['PUT'])
@jwt_required()
def activate_client(user_id):

    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para gestionar clientes",
            "FORBIDDEN",
            403
        )

    client = User.query.get(user_id)

    if not client:
        return error_response(
            "El cliente solicitado no existe",
            "CLIENT_NOT_FOUND",
            404
        )

    if client.role != "club_owner":
        return error_response(
            "Solo los clientes pueden ser reactivados",
            "INVALID_CLIENT",
            400
        )

    client.is_active = True
    db.session.commit()

    return jsonify({
        "message": "Cliente reactivado correctamente",
        "client": client.serialize()
    }), 200

################################### CLUB #############################################

@api.route("/club/users", methods=["POST"])
@jwt_required()
def create_club_user():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede crear usuarios",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    body = request.get_json() or {}

    full_name = body.get("full_name")
    email = body.get("email")

    if email:
        email = email.strip().lower()
    role = body.get("role")

    if not full_name:
        return error_response(
            "Nombre completo requerido",
            "FULL_NAME_REQUIRED",
            400
        )

    if not email:
        return error_response(
            "Email requerido",
            "EMAIL_REQUIRED",
            400
        )

    if role not in ["coach", "staff"]:
        return error_response(
            "Rol inválido",
            "INVALID_ROLE",
            400
        )

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        return error_response(
            "Ya existe un usuario con ese email",
            "EMAIL_ALREADY_EXISTS",
            409
        )

    temp_password = generate_temp_password()

    hashed_password = bcrypt.generate_password_hash(temp_password).decode("utf-8")

    new_user = User(
        full_name=full_name,
        email=email,
        password=hashed_password,
        role=role,
        first_login=True,
        club_id=club.id
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "message": "Usuario del club creado",
        "temporary_password": temp_password,
        "user": new_user.serialize()
    }), 201

@api.route("/club", methods=["PUT"])
@jwt_required()
def update_club():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede actualizar la información",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    body = request.get_json() or {}

    location = body.get("location")

    if not location:
        return error_response(
            "La ubicación es obligatoria",
            "LOCATION_REQUIRED",
            400
        )

    club.location = location

    db.session.commit()

    return jsonify({
        "message": "Información del club actualizada",
        "club": club.serialize()
    }), 200

@api.route("/club/dashboard", methods=["GET"])
@jwt_required()
def club_dashboard():

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver el dashboard",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    total_teams = Team.query.filter_by(club_id=club.id).count()

    total_players = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id
    ).count()

    active_players = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id,
        TeamPlayer.status == "active"
    ).count()

    injured_players = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id,
        TeamPlayer.status == "injured"
    ).count()

    inactive_players = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id,
        TeamPlayer.status == "inactive"
    ).count()

    total_trainings = TrainingSession.query.join(Team).filter(
        Team.club_id == club.id
    ).count()

    today = datetime.utcnow().date()

    
    next_match = MatchSession.query.join(Team).filter(
        Team.club_id == club.id,
        MatchSession.is_completed == False,
        MatchSession.date >= today
    ).order_by(MatchSession.date.asc()).first()

   
    if not next_match:
        next_match = MatchSession.query.join(Team).filter(
            Team.club_id == club.id,
            MatchSession.is_completed == False,
            MatchSession.date < today
        ).order_by(MatchSession.date.desc()).first()

    return jsonify({
        "club": club.serialize(),
        "stats": {
            "total_teams": total_teams,
            "total_players": total_players,
            "active_players": active_players,
            "injured_players": injured_players,
            "inactive_players": inactive_players,
            "total_trainings": total_trainings
        },
        "next_match": {
            **next_match.serialize(),
            "team_name": next_match.team.name
        } if next_match else None
    }), 200

@api.route("/teams/<string:team_id>/players/<string:player_id>", methods=["DELETE"])
@jwt_required()
def remove_player_from_team(team_id, player_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response("No tienes permisos", "FORBIDDEN", 403)

    team = Team.query.get(team_id)

    if not team or team.club_id != user.club_id:
        return error_response("Equipo no encontrado", "TEAM_NOT_FOUND", 404)

    membership = TeamPlayer.query.filter_by(
        team_id=team.id,
        player_id=player_id
    ).first()

    if not membership:
        return error_response(
            "El jugador no pertenece a esta categoría",
            "PLAYER_MEMBERSHIP_NOT_FOUND",
            404
        )

    db.session.delete(membership)
    db.session.commit()

    return jsonify({
        "message": "Jugador removido de la categoría"
    }), 200

############################################## TEAMS #############################################
@api.route("/teams", methods=["POST"])
@jwt_required()
def create_team():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede crear categorías",
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

    name = body.get("name")
    gender = body.get("gender")

    # ✅ normalización fuerte
    if name:
        name = " ".join(name.strip().split())

    if not name:
        return error_response(
            "Nombre de la categoría requerido",
            "TEAM_NAME_REQUIRED",
            400
        )

    allowed_gender = ["female", "male", "mixed"]

    if gender not in allowed_gender:
        return error_response(
            "La rama es inválida",
            "INVALID_TEAM_GENDER",
            400
        )

    # ✅ búsqueda robusta ignorando mayúsculas
    existing_team = Team.query.filter(
        Team.club_id == user.club_id,
        Team.gender == gender,
        func.lower(Team.name) == name.lower()
    ).first()

    if existing_team:
        return error_response(
            "Ya existe esta categoría en esa rama",
            "TEAM_ALREADY_EXISTS",
            409
        )

    team = Team(
        name=name,
        gender=gender,
        club_id=user.club_id
    )

    db.session.add(team)
    db.session.commit()

    return jsonify({
        "message": "Categoría creada correctamente",
        "team": team.serialize()
    }), 201

@api.route("/teams", methods=["GET"])
@jwt_required()
def get_teams():

    user = get_current_user()
    
    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    teams = Team.query.filter_by(club_id=user.club_id)\
        .order_by(Team.name)\
        .all()

    return jsonify({
        "teams": [t.serialize() for t in teams]
    }), 200

@api.route("/teams/<string:team_id>", methods=["GET"])
@jwt_required()
def get_team_detail(team_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
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
            "No tienes acceso a esta categoría",
            "FORBIDDEN",
            403
        )

    total_players = TeamPlayer.query.filter_by(team_id=team.id).count()

    return jsonify({
        "team": team.serialize(),
        "stats": {
            "total_players": total_players
        }
    }), 200

@api.route("/teams/<string:team_id>", methods=["DELETE"])
@jwt_required()
def delete_team(team_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede eliminar categorías",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
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
            "No tienes permisos para eliminar esta categoría",
            "FORBIDDEN",
            403
        )

    players_count = TeamPlayer.query.filter_by(team_id=team.id).count()

    if players_count > 0:
        return error_response(
            "No puedes eliminar una categoría que tiene jugadores registrados",
            "TEAM_HAS_PLAYERS",
            409
        )

    trainings_count = TrainingSession.query.filter_by(team_id=team.id).count()

    if trainings_count > 0:
        return error_response(
            "No puedes eliminar una categoría con entrenamientos históricos",
            "TEAM_HAS_TRAININGS",
            409
        )

    db.session.delete(team)
    db.session.commit()

    return jsonify({
        "message": "Equipo eliminado correctamente"
    }), 200

################################################ PLAYERS #############################################
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

    body = request.get_json() or {}
    
    first_name = body.get("first_name")
    last_name = body.get("last_name")
    player_number = body.get("player_number")
    sex = body.get("sex")
    birth_date = body.get("birth_date")
    status = body.get("status", "active")
    team_id = body.get("team_id")

    main_position = (body.get("main_position") or "").strip().lower() or None

    if main_position and main_position not in ALLOWED_POSITIONS:
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
                "Categoría no encontrada",
                "TEAM_NOT_FOUND",
                404
            )

        if team.club_id != user.club_id:
            return error_response(
                "No tienes permisos para registrar jugadores en esta categoría",
                "FORBIDDEN",
                403
            )

        if team.gender != "mixed" and team.gender != sex:
            return error_response(
                "El sexo del jugador no coincide con la rama de la categoría",
                "PLAYER_GENDER_MISMATCH",
                400
            )

        existing_membership = TeamPlayer.query.filter_by(
            team_id=team.id,
            player_number=player_number
        ).first()

        if existing_membership:
            return error_response(
                "Ya existe un jugador con ese número en esta categoría",
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

    memberships = TeamPlayer.query.filter_by(team_id=team.id)\
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

    players = Player.query.filter_by(
        club_id=user.club_id
    ).order_by(Player.created_at.desc()).all()

    serialized_players = []

    for player in players:
        membership = player.team_memberships[0] if player.team_memberships else None

        serialized_players.append({
            **player.serialize(),
            "team_id": membership.team_id if membership else None,
            "player_number": membership.player_number if membership else None,
            "status": membership.status if membership else "active",
            "teams": [
                {
                    "id": m.team.id,
                    "name": m.team.name,
                    "player_number": m.player_number,
                    "status": m.status
                }
                for m in player.team_memberships
            ]
        })

    return jsonify({
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
        player_id=player.id
    ).first()

    if existing:
        return error_response(
            "El jugador ya pertenece al equipo",
            "PLAYER_ALREADY_IN_TEAM",
            409
        )

    duplicated_number = TeamPlayer.query.filter_by(
        team_id=team.id,
        player_number=player_number
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

    main_position = (body.get("main_position") or "").strip().lower() or None

    if main_position and main_position not in ALLOWED_POSITIONS:
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
        player_id=player.id
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
        membership = TeamPlayer.query.filter_by(
            player_id=player.id,
            team_id=team_id
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
            TeamPlayer.player_id != player.id
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
        team_id=team_id
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

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para eliminar jugadores",
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

    # 🚨 protección histórica
    attendance_exists = Attendance.query.filter_by(
        player_id=player.id
    ).first()

    match_exists = MatchPlayer.query.filter_by(
        player_id=player.id
    ).first()

    if attendance_exists or match_exists:
        return error_response(
            "No puedes eliminar una jugadora con historial registrado",
            "PLAYER_HAS_HISTORY",
            409
        )

    for membership in memberships:
        db.session.delete(membership)

    db.session.delete(player)
    db.session.commit()

    return jsonify({
        "message": "Jugador eliminado correctamente"
    }), 200

########################################### ATTENDANCE #############################################
@api.route("/trainings/<string:training_id>/attendance", methods=["POST"])
@jwt_required()
def save_attendance(training_id):

    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para registrar asistencia",
            "FORBIDDEN",
            403
        )

    training = TrainingSession.query.get(training_id)

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    team = Team.query.get(training.team_id)

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este entrenamiento",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}
    attendance_list = body.get("attendance")

    if not attendance_list:
        return error_response(
            "Lista de asistencia requerida",
            "ATTENDANCE_REQUIRED",
            400
        )

    Attendance.query.filter_by(session_id=training.id).delete()

    allowed_status = ["present", "late", "absent"]

    for item in attendance_list:

        player_id = item.get("player_id")
        status = item.get("status", "present")

        if status not in allowed_status:
            return error_response(
                "Estado de asistencia inválido",
                "INVALID_ATTENDANCE_STATUS",
                400
            )

        attendance = Attendance(
            session_id=training.id,
            player_id=player_id,
            status=status
        )

        db.session.add(attendance)

    db.session.commit()

    return jsonify({
        "message": "Asistencia guardada correctamente"
    }), 200

@api.route("/trainings/<string:training_id>/attendance", methods=["GET"])
@jwt_required()
def get_attendance(training_id):

    user = get_current_user()

    training = TrainingSession.query.get(training_id)

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    team = Team.query.get(training.team_id)

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    attendance = Attendance.query.filter_by(
        session_id=training.id
    ).all()

    return jsonify({
        "attendance": [a.serialize() for a in attendance]
    }), 200

@api.route("/trainings/<string:training_id>/players", methods=["GET"])
@jwt_required()
def get_training_players(training_id):
    user = get_current_user()

    training = TrainingSession.query.get(training_id)

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    team = Team.query.get(training.team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    snapshot = TrainingPlayer.query.filter_by(
        training_id=training.id
    ).order_by(TrainingPlayer.player_number).all()

    players = []

    for row in snapshot:
        if not row.player:
            continue

        players.append({
            "id": row.player.id,
            "first_name": row.player.first_name,
            "last_name": row.player.last_name,
            "player_number": row.player_number,
            "sex": row.player.sex
        })

    return jsonify({
        "players": players
    }), 200

@api.route("/players/<string:player_id>/attendance", methods=["GET"])
@jwt_required()
def get_player_attendance(player_id):

    user = get_current_user()

    player = Player.query.get(player_id)

    if not player:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    memberships = TeamPlayer.query.filter_by(
        player_id=player.id
    ).all()

    if player.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )


    for membership in memberships:
        team = Team.query.get(membership.team_id)

        if not team or team.club_id != user.club_id:
            return error_response(
                "No tienes acceso",
                "FORBIDDEN",
                403
            )
        
    attendance_records = Attendance.query.join(TrainingSession).filter(
        Attendance.player_id == player.id
    ).order_by(TrainingSession.date.desc()).all()

    history = []
    present = 0
    late = 0
    absent = 0

    for record in attendance_records:
        if record.status == "present":
            present += 1
        elif record.status == "late":
            late += 1
        elif record.status == "absent":
            absent += 1

        history.append({
            "training_id": record.session_id,
            "date": record.session.date.isoformat(),
            "location": record.session.location,
            "status": record.status
        })

    total = present + late + absent
    attendance_rate = round((present / total) * 100) if total > 0 else 0

    return jsonify({
        "player": {
            **player.serialize(),
            "teams": [
                {
                    "id": m.team.id,
                    "name": m.team.name,
                    "gender": m.team.gender,
                    "player_number": m.player_number,
                    "status": m.status
                }
                for m in memberships
            ]
        },
        "summary": {
            "present": present,
            "late": late,
            "absent": absent,
            "total_sessions": total,
            "attendance_rate": attendance_rate
        },
        "history": history
    }), 200

############################################ TRAININGS ##############################################
@api.route("/trainings", methods=["POST"])
@jwt_required()
def create_training():

    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    team_id = body.get("team_id")
    date = body.get("date")
    location = body.get("location")

    # ✅ VALIDACIONES VAN AQUÍ
    if not team_id:
        return error_response(
            "La categoría es obligatoria",
            "TEAM_ID_REQUIRED",
            400
        )

    if not date:
        return error_response(
            "La fecha del entrenamiento es obligatoria",
            "TRAINING_DATE_REQUIRED",
            400
        )

    if not location or not str(location).strip():
        return error_response(
            "La ubicación del entrenamiento es obligatoria",
            "TRAINING_LOCATION_REQUIRED",
            400
        )

    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return error_response(
            "Formato de fecha inválido. Usa YYYY-MM-DD",
            "INVALID_DATE_FORMAT",
            400
        )

    location = location.strip()

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

    training = TrainingSession(
        team_id=team.id,
        date=parsed_date,
        location=location,
        created_by=user.id
    )

    db.session.add(training)
    db.session.flush()

    current_roster = TeamPlayer.query.filter_by(
        team_id=team.id
    ).all()

    for member in current_roster:
        snapshot = TrainingPlayer(
            training_id=training.id,
            player_id=member.player_id,
            player_number=member.player_number
        )
        db.session.add(snapshot)

    db.session.commit()

    return jsonify({
        "message": "Entrenamiento creado",
        "training": training.serialize()
    }), 201

@api.route("/teams/<string:team_id>/trainings", methods=["GET"])
@jwt_required()
def get_team_trainings(team_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver entrenamientos",
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

    # Seguridad multi-tenant
    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este equipo",
            "FORBIDDEN",
            403
        )

    trainings = TrainingSession.query.filter_by(team_id=team.id)\
        .order_by(TrainingSession.date.desc())\
        .all()

    return jsonify({
        "team": team.serialize(),
        "total_trainings": len(trainings),
        "trainings": [t.serialize() for t in trainings]
    }), 200

@api.route("/trainings", methods=["GET"])
@jwt_required()
def get_all_trainings():

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver entrenamientos",
            "FORBIDDEN",
            403
        )

    trainings = TrainingSession.query.join(Team).filter(
        Team.club_id == user.club_id
    ).order_by(TrainingSession.date.desc()).all()

    return jsonify({
        "total_trainings": len(trainings),
        "trainings": [
        {
            **t.serialize(),
            "team_name": t.team.name
        }
        for t in trainings
    ]
    }), 200
############################################ ONBOARDING #############################################
@api.route("/onboarding/status", methods=["GET"])
@jwt_required()
def onboarding_status():
    print("ONBOARDING STATUS HIT")

    user = get_current_user()

    if user.role == "system_admin":
        return jsonify({
            "step": 4,
            "status": "completed",
            "club": None
        }), 200

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    # STEP 1 — configurar club
    if not club.location:
        return jsonify({
            "step": 1,
            "status": "pending",
            "club": club.serialize()
        }), 200

    # STEP 2 — verificar si existen equipos
    teams_count = Team.query.filter_by(club_id=club.id).count()

    if teams_count == 0:
        return jsonify({
            "step": 2,
            "status": "pending",
            "club": club.serialize()
        }), 200

    # STEP 3 — verificar jugadores
    players_count = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id
    ).count()

    if players_count == 0:
        return jsonify({
            "step": 3,
            "status": "pending",
            "club": club.serialize()
        }), 200

    # STEP 4 — onboarding completo
    return jsonify({
        "step": 4,
        "status": "completed",
        "club": club.serialize()
    }), 200

@api.route("/onboarding/complete", methods=["POST"])
@jwt_required()
def complete_onboarding():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede completar el onboarding",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    players_count = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id
    ).count()

    if players_count == 0:
        return error_response(
            "Debes registrar al menos un jugador antes de activar el sistema",
            "ONBOARDING_REQUIRES_PLAYERS",
            400
        )

    user.first_login = False
    db.session.commit()

    return jsonify({
        "message": "Sistema activado correctamente"
    }), 200


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

    body = request.get_json() or {}

    team_id = body.get("team_id")
    date = body.get("date")
    opponent_name = body.get("opponent_name")
    match_type = body.get("match_type", "official")
    location = body.get("location")
    notes = body.get("notes")

    if opponent_name:
        opponent_name = opponent_name.strip()
    
    if not team_id:
        return error_response(
            "La categoría es obligatoria",
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
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
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
            "No tienes acceso a esta categoría",
            "FORBIDDEN",
            403
        )

    match = MatchSession(
        team_id=team.id,
        date=parsed_date,
        opponent_name=opponent_name,
        match_type=match_type,
        location=location,
        notes=notes,
        created_by=user.id
    )

    db.session.add(match)
        
    db.session.flush()

    current_roster = TeamPlayer.query.filter_by(
        team_id=team.id
    ).all()

    for member in current_roster:
        snapshot = MatchPlayer(
            match_id=match.id,
            player_id=member.player_id,
            player_number=member.player_number,
            is_called=False,
            attendance_status=None,
            did_play=False
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

    selected_ids = {
        item.get("player_id")
        for item in players
        if item.get("player_id")
    }

    rows = MatchPlayer.query.filter_by(match_id=match.id).all()

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

@api.route("/matches/<string:match_id>/roster/status", methods=["PUT"])
@jwt_required()
def update_match_status(match_id):
    user = get_current_user()

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response("Partido no encontrado", "MATCH_NOT_FOUND", 404)

    if match.team.club_id != user.club_id:
        return error_response("No tienes acceso", "FORBIDDEN", 403)

    body = request.get_json() or {}
    players = body.get("players")

    if not players:
        return error_response("Lista requerida", "MATCH_STATUS_REQUIRED", 400)

    for item in players:
        match_player_id = item.get("match_player_id")
        status = item.get("attendance_status")
        position = (item.get("position") or "").strip().lower()

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

        if status in PLAYABLE_MATCH_STATUSES:
            if not position:
                position = row.player.main_position

            if not position:
                return error_response(
                    "La posición es obligatoria para jugadoras presentes o tarde",
                    "POSITION_REQUIRED",
                    400
                )

            if position not in ALLOWED_POSITIONS:
                return error_response(
                    "Posición inválida",
                    "INVALID_POSITION",
                    400
                )

            row.position = position
        else:
            row.position = None
            row.did_play = False
            row.is_on_court = False

        row.attendance_status = status

    match.match_step = max(match.match_step, 2)

    db.session.commit()

    return jsonify({
        "message": "Estado del día actualizado"
    }), 200

@api.route("/matches/<string:match_id>", methods=["GET"])
@jwt_required()
def get_match_detail(match_id):
    user = get_current_user()

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

@api.route("/matches/<string:match_id>/roster", methods=["GET"])
@jwt_required()
def get_match_roster(match_id):
    user = get_current_user()

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
            "position": row.position or row.player.main_position,
        })

    return jsonify({
        "players": players,
        "synced_count": synced_count
    }), 200

@api.route("/matches/<string:match_id>/starting-lineup", methods=["PUT"])
@jwt_required()
def save_starting_lineup(match_id):
    user = get_current_user()

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
    players = body.get("players")

    if not players:
        return error_response(
            "Debes seleccionar las jugadoras iniciales",
            "STARTING_LINEUP_REQUIRED",
            400
        )

    if len(players) != 6:
        return error_response(
            "Debes seleccionar exactamente 6 jugadoras en cancha",
            "STARTING_LINEUP_MUST_HAVE_6",
            400
        )

    selected_ids = set(players)

    rows = MatchPlayer.query.filter_by(match_id=match.id).all()

    valid_rows = []

    for row in rows:
        if row.id in selected_ids:
            valid_rows.append(row)

    if len(valid_rows) != 6:
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

    player_out_id = body.get("player_out_id")
    player_in_id = body.get("player_in_id")

    try:
        set_number = int(body.get("set_number", 1))
    except (TypeError, ValueError):
        return error_response(
            "Set inválido",
            "INVALID_SET_NUMBER",
            400
        )

    if set_number < 1 or set_number > 5:
        return error_response(
            "El set debe estar entre 1 y 5",
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
    players = body.get("players")

    if not players:
        return error_response(
            "Lista requerida",
            "MATCH_PARTICIPATION_REQUIRED",
            400
        )

    for item in players:
        match_player_id = item.get("match_player_id")

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

        if row.attendance_status not in PLAYABLE_MATCH_STATUSES:
            return error_response(
                "La jugadora no puede marcar participación con ese estado",
                "PLAYER_NOT_ELIGIBLE_FOR_PARTICIPATION",
                400
            )

        did_play = bool(item.get("did_play", False))
        position = (item.get("position") or row.player.main_position or "").strip().lower()

        if did_play and not position:
            return error_response(
                "La posición es obligatoria si la jugadora participó",
                "POSITION_REQUIRED",
                400
            )

        if position and position not in ALLOWED_POSITIONS:
            return error_response(
                "Posición inválida",
                "INVALID_POSITION",
                400
            )

        row.did_play = did_play
        row.position = position if did_play else None

    match.match_step = max(match.match_step, 3)

    db.session.commit()

    return jsonify({
        "message": "Participación guardada"
    }), 200

@api.route("/match-players/<string:match_player_id>/stats", methods=["POST"])
@jwt_required()
def save_match_stats(match_player_id):
    user = get_current_user()

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

    new_position = validated_stats.get("position")

    if new_position:
        row.position = new_position
    elif not row.position:
        row.position = row.player.main_position

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
                "is_completed": match.is_completed
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

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response("No tienes acceso", "FORBIDDEN", 403)

    body = request.get_json() or {}

    try:
        home_sets = int(body.get("home_sets", 0))
        opponent_sets = int(body.get("opponent_sets", 0))
    except (TypeError, ValueError):
        return error_response(
            "Los sets deben ser números enteros",
            "INVALID_MATCH_RESULT",
            400
        )

    # ✅ VALIDACIÓN DE NEGATIVOS
    if home_sets < 0 or opponent_sets < 0:
        return error_response(
            "Los sets no pueden ser negativos",
            "INVALID_MATCH_RESULT",
            400
        )

    # ✅ NADIE PUEDE PASAR DE 3
    if home_sets > 3 or opponent_sets > 3:
        return error_response(
            "Ningún equipo puede superar 3 sets",
            "INVALID_MATCH_RESULT",
            400
        )

    # ✅ NO HAY EMPATE
    if home_sets == opponent_sets:
        return error_response(
            "No puede haber empate en sets",
            "INVALID_MATCH_RESULT",
            400
        )

    # ✅ EL GANADOR DEBE TENER 3
    if max(home_sets, opponent_sets) != 3:
        return error_response(
            "Uno de los equipos debe ganar 3 sets",
            "INVALID_MATCH_RESULT",
            400
        )

    # ✅ EL PERDEDOR SOLO PUEDE TENER 0,1,2
    if min(home_sets, opponent_sets) > 2:
        return error_response(
            "El equipo perdedor no puede superar 2 sets",
            "INVALID_MATCH_RESULT",
            400
        )

    match.home_sets = home_sets
    match.opponent_sets = opponent_sets
    match.result = "win" if home_sets > opponent_sets else "loss"

    if max(home_sets, opponent_sets) == 3:
        match.is_completed = True

    db.session.commit()

    return jsonify({
        "message": "Resultado guardado",
        "match": match.serialize()
    }), 200

############################################ MATCH EVENTS #############################################


VALID_EVENT_ACTIONS = [
    "attack", "reception", "serve",
    "block", "set", "defense"
]

VALID_EVENT_RESULTS_BY_ACTION = {
    "attack": ["positive", "neutral", "error"],
    "reception": ["positive", "neutral", "negative"],
    "defense": ["positive", "neutral", "negative"],
    "set": ["positive", "neutral", "error"],
    "serve": ["in", "ace", "error"],
    "block": ["point", "neutral", "error"],
}


@api.route("/match-events", methods=["POST"])
@jwt_required()
def create_match_event():
    user = get_current_user()
    body = request.get_json() or {}

    match_id = body.get("match_id")
    match_player_id = body.get("match_player_id")
    action = body.get("action_type")
    result = body.get("result")

    try:
        set_number = int(body.get("set_number", 1))
    except (TypeError, ValueError):
        return error_response(
            "Set inválido",
            "INVALID_SET_NUMBER",
            400
        )

    if set_number < 1 or set_number > 5:
        return error_response(
            "El set debe estar entre 1 y 5",
            "INVALID_SET_NUMBER",
            400
        )

    
    if not match_id or not match_player_id:
        return error_response(
            "Datos incompletos",
            "MATCH_EVENT_REQUIRED",
            400
        )

    if action not in VALID_EVENT_ACTIONS:
        return error_response(
            "Acción inválida",
            "INVALID_EVENT_ACTION",
            400
        )

    allowed_results = VALID_EVENT_RESULTS_BY_ACTION.get(action, [])

    if result not in allowed_results:
        return error_response(
            "Resultado inválido para esta acción",
            "INVALID_EVENT_RESULT",
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

    match_player_id = event.match_player_id

    db.session.delete(event)
    db.session.flush()

    recalculate_player_match_stats(match_player_id)

    db.session.commit()

    return jsonify({
        "message": "Evento eliminado correctamente"
    }), 200