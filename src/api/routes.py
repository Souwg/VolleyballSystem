"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
from flask import Flask, request, jsonify, url_for, Blueprint
from src.api.models import db, User, Club, Player, Team, Attendance, TrainingSession, TokenBlockedList, RefreshToken
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

    total_players = Player.query.join(Team).filter(
        Team.club_id == club.id
    ).count()

    active_players = Player.query.join(Team).filter(
        Team.club_id == club.id,
        Player.status == "active"
    ).count()

    injured_players = Player.query.join(Team).filter(
        Team.club_id == club.id,
        Player.status == "injured"
    ).count()

    inactive_players = Player.query.join(Team).filter(
        Team.club_id == club.id,
        Player.status == "inactive"
    ).count()

    total_trainings = TrainingSession.query.join(Team).filter(
        Team.club_id == club.id
    ).count()

    return jsonify({
        "club": club.serialize(),
        "stats": {
            "total_teams": total_teams,
            "total_players": total_players,
            "active_players": active_players,
            "injured_players": injured_players,
            "inactive_players": inactive_players,
            "total_trainings": total_trainings
        }
    }), 200

############################################## TEAMS #############################################
@api.route("/teams", methods=["POST"])
@jwt_required()
def create_team():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede crear equipos",
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

    if name:
        name = name.strip()

    if not name:
        return error_response(
            "Nombre del equipo requerido",
            "TEAM_NAME_REQUIRED",
            400
        )

    existing_team = Team.query.filter_by(
        name=name,
        club_id=user.club_id
    ).first()

    if existing_team:
        return error_response(
            "Ya existe un equipo con ese nombre en el club",
            "TEAM_ALREADY_EXISTS",
            409
        )

    team = Team(
        name=name,
        club_id=user.club_id
    )

    db.session.add(team)
    db.session.commit()

    return jsonify({
        "message": "Equipo creado correctamente",
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
            "No tienes acceso a este equipo",
            "FORBIDDEN",
            403
        )

    total_players = Player.query.filter_by(team_id=team.id).count()

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
            "Solo el dueño del club puede eliminar equipos",
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

    # Protección multi-tenant
    if team.club_id != user.club_id:
        return error_response(
            "No tienes permisos para eliminar este equipo",
            "FORBIDDEN",
            403
        )

    players_count = Player.query.filter_by(team_id=team.id).count()

    if players_count > 0:
        return error_response(
            "No puedes eliminar un equipo que tiene jugadores registrados",
            "TEAM_HAS_PLAYERS",
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

    if not team_id:
        return error_response(
            "El equipo es obligatorio",
            "TEAM_ID_REQUIRED",
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

    existing_player = Player.query.filter_by(
        player_number=player_number,
        team_id=team.id
    ).first()

    if existing_player:
        return error_response(
            "Ya existe un jugador con ese número en este equipo",
            "PLAYER_NUMBER_DUPLICATED",
            409
        )

    parsed_birth_date = None
    if birth_date:
        try:
            parsed_birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()

            if parsed_birth_date > datetime.utcnow().date():
                return error_response(
                    "La fecha de nacimiento no puede ser futura",
                    "INVALID_BIRTH_DATE",
                    400
                )
        
        except ValueError:
            return error_response(
                "Formato de fecha inválido. Usa YYYY-MM-DD",
                "INVALID_DATE_FORMAT",
                400
            )

    player = Player(
        first_name=first_name,
        last_name=last_name,
        player_number=player_number,
        sex=sex,
        birth_date=parsed_birth_date,
        status=status,
        team_id=team.id
    )

    db.session.add(player)
    db.session.commit()

    return jsonify({
        "message": "Jugador registrado correctamente",
        "player": player.serialize()
    }), 201

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
            "No tienes acceso a este equipo",
            "FORBIDDEN",
            403
        )

    players = Player.query.filter_by(team_id=team.id)\
        .order_by(Player.player_number)\
        .all()

    return jsonify({
        "team": team.serialize(),
        "total_players": len(players),
        "players": [p.serialize() for p in players]
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

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver jugadores",
            "FORBIDDEN",
            403
        )

    players = Player.query.join(Team)\
        .filter(Team.club_id == user.club_id)\
        .order_by(Player.player_number)\
        .all()

    return jsonify({
        "total_players": len(players),
        "players": [p.serialize() for p in players]
    }), 200

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

    if not player:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    team = Team.query.get(player.team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "No tienes permisos para modificar este jugador",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    first_name = body.get("first_name")
    last_name = body.get("last_name")
    player_number = body.get("player_number")
    sex = body.get("sex")
    birth_date = body.get("birth_date")
    team_id = body.get("team_id")


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

    if player_number is None:
        return error_response(
            "Número del jugador requerido",
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

    if not team_id:
        return error_response(
            "El equipo es obligatorio",
            "TEAM_ID_REQUIRED",
            400
        )

    new_team = Team.query.get(team_id)

    if not new_team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if new_team.club_id != user.club_id:
        return error_response(
            "No puedes asignar jugadores a equipos de otro club",
            "FORBIDDEN",
            403
        )

    existing_player = Player.query.filter(
        Player.player_number == player_number,
        Player.team_id == team_id,
        Player.id != player.id
    ).first()

    if existing_player:
        return error_response(
            "Ya existe un jugador con ese número en ese equipo",
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
    player.first_name = first_name
    player.last_name = last_name
    player.player_number = player_number
    player.sex = sex
    player.birth_date = parsed_birth_date
    player.team_id = team_id

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

    if not player:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    team = Team.query.get(player.team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "No tienes permisos para modificar este jugador",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}
    status = body.get("status")

    allowed_status = ["active", "injured", "inactive"]

    if status not in allowed_status:
        return error_response(
            "Estado del jugador inválido",
            "INVALID_PLAYER_STATUS",
            400
        )

    player.status = status
    db.session.commit()

    return jsonify({
        "message": "Estado del jugador actualizado correctamente",
        "player": player.serialize()
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

    if not player:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    team = Team.query.get(player.team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "No tienes permisos para eliminar este jugador",
            "FORBIDDEN",
            403
        )

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

    # borrar asistencia anterior
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

    team = Team.query.get(player.team_id)

    if team.club_id != user.club_id:
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

    attendance_rate = 0
    if total > 0:
        attendance_rate = round((present / total) * 100)

    return jsonify({
        "player": player.serialize(),
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
    start_time = body.get("start_time")
    location = body.get("location")

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
        date=datetime.strptime(date, "%Y-%m-%d").date(),
        location=location,
        created_by=user.id
    )

    db.session.add(training)
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
    players_count = Player.query.join(Team).filter(
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

    players_count = Player.query.join(Team).filter(
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

