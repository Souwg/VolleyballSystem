import os
import re

from flask import current_app, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.orm import joinedload

from src.api.api_blueprint import api
from src.api.currency_registry import (
    normalize_currency_code,
    serialize_supported_currencies,
)
from src.api.email_service import send_welcome_email
from src.api.extensions import bcrypt
from src.api.models import (
    db,
    AdministrativeArea,
    Club,
    Country,
    RefreshToken,
    Sport,
    User,
)
from src.api.time_utils import (
    get_suggested_timezone,
    normalize_iana_timezone,
)
from src.api.utils import error_response, generate_temp_password, get_current_user


@api.route('/admin/currencies', methods=['GET'])
@jwt_required()
def get_supported_currencies():
    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para consultar monedas",
            "FORBIDDEN",
            403
        )

    return jsonify({
        "currencies": serialize_supported_currencies()
    }), 200


@api.route('/admin/sports', methods=['GET'])
@jwt_required()
def get_active_sports():
    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para consultar deportes",
            "FORBIDDEN",
            403
        )

    sports = Sport.query.filter_by(
        is_active=True
    ).order_by(
        Sport.name.asc(),
        Sport.code.asc()
    ).all()

    return jsonify({
        "sports": [sport.serialize() for sport in sports]
    }), 200


@api.route('/admin/countries', methods=['GET'])
@jwt_required()
def get_active_countries():
    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para consultar países",
            "FORBIDDEN",
            403
        )

    countries = Country.query.filter_by(
        is_active=True
    ).order_by(
        Country.name.asc(),
        Country.code.asc()
    ).all()

    return jsonify({
        "countries": [
            {
                **country.serialize(),
                "suggested_timezone": get_suggested_timezone(country.code)
            }
            for country in countries
        ]
    }), 200


@api.route(
    '/admin/countries/<string:country_id>/areas',
    methods=['GET']
)
@jwt_required()
def get_active_administrative_areas(country_id):
    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para consultar regiones",
            "FORBIDDEN",
            403
        )

    country = Country.query.get(country_id)

    if not country:
        return error_response(
            "El país seleccionado no es válido",
            "INVALID_COUNTRY",
            404
        )

    if not country.is_active:
        return error_response(
            "El país seleccionado no está disponible para nuevas altas",
            "COUNTRY_NOT_AVAILABLE",
            400
        )

    areas = AdministrativeArea.query.filter_by(
        country_id=country.id,
        is_active=True
    ).order_by(
        AdministrativeArea.name.asc(),
        AdministrativeArea.code.asc()
    ).all()

    return jsonify({
        "country": country.serialize(),
        "areas": [area.serialize() for area in areas]
    }), 200


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
    club_name = body.get("club_name")
    sport_id = body.get("sport_id")
    country_id = body.get("country_id")
    administrative_area_id = body.get("administrative_area_id")
    city = body.get("city")
    timezone = body.get("timezone")
    currency_code = body.get("currency_code")

    if full_name:
        full_name = " ".join(str(full_name).strip().split())

    if email:
        email = email.strip().lower()

    if club_name:
        club_name = " ".join(str(club_name).strip().split())

    if not full_name or not str(full_name).strip():
        return error_response(
            "Nombre completo es obligatorio",
            "FULL_NAME_REQUIRED",
            400
        )

    if not email:
        return error_response(
            "Email es obligatorio",
            "EMAIL_REQUIRED",
            400
        )

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return error_response(
            "Email inválido",
            "INVALID_EMAIL",
            400
        )

    if not club_name or not str(club_name).strip():
        return error_response(
            "Nombre del club es obligatorio",
            "CLUB_NAME_REQUIRED",
            400
        )

    if not str(currency_code or "").strip():
        return error_response(
            "La moneda es obligatoria",
            "CURRENCY_REQUIRED",
            400
        )

    currency_code = normalize_currency_code(currency_code)

    if not currency_code:
        return error_response(
            "La moneda seleccionada no es válida",
            "INVALID_CURRENCY",
            400
        )

    if not sport_id:
        return error_response(
            "El deporte es obligatorio",
            "SPORT_REQUIRED",
            400
        )

    sport = Sport.query.get(str(sport_id).strip())

    if not sport:
        return error_response(
            "El deporte seleccionado no es válido",
            "INVALID_SPORT",
            400
        )

    if not sport.is_active:
        return error_response(
            "El deporte seleccionado no está disponible para nuevas altas",
            "SPORT_NOT_AVAILABLE",
            400
        )

    if not country_id:
        return error_response(
            "El país es obligatorio",
            "COUNTRY_REQUIRED",
            400
        )

    country = Country.query.get(str(country_id).strip())

    if not country:
        return error_response(
            "El país seleccionado no es válido",
            "INVALID_COUNTRY",
            400
        )

    if not country.is_active:
        return error_response(
            "El país seleccionado no está disponible para nuevas altas",
            "COUNTRY_NOT_AVAILABLE",
            400
        )

    if not administrative_area_id:
        return error_response(
            "El estado, provincia o región es obligatorio",
            "ADMINISTRATIVE_AREA_REQUIRED",
            400
        )

    administrative_area = AdministrativeArea.query.get(
        str(administrative_area_id).strip()
    )

    if not administrative_area:
        return error_response(
            "El estado, provincia o región no es válido",
            "INVALID_ADMINISTRATIVE_AREA",
            400
        )

    if not administrative_area.is_active:
        return error_response(
            "El estado, provincia o región no está disponible",
            "ADMINISTRATIVE_AREA_NOT_AVAILABLE",
            400
        )

    if administrative_area.country_id != country.id:
        return error_response(
            "La región seleccionada no pertenece al país indicado",
            "AREA_COUNTRY_MISMATCH",
            400
        )

    city = str(city or "").strip()

    if not city:
        return error_response(
            "La ciudad es obligatoria",
            "CITY_REQUIRED",
            400
        )

    if len(city) > 120:
        return error_response(
            "La ciudad no puede superar los 120 caracteres",
            "CITY_TOO_LONG",
            400
        )

    if not str(timezone or "").strip():
        return error_response(
            "La zona horaria es obligatoria",
            "TIMEZONE_REQUIRED",
            400
        )

    timezone = normalize_iana_timezone(timezone)

    if not timezone:
        return error_response(
            "La zona horaria seleccionada no es válida",
            "INVALID_TIMEZONE",
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
        full_name=full_name.strip(),
        email=email,
        password=hashed_password,
        first_login=True,
        role="club_owner"
    )

    try:
        db.session.add(new_user)
        db.session.flush()

        club = Club(
            name=club_name.strip(),
            location=city,
            state=administrative_area.name,
            owner_id=new_user.id,
            sport_id=sport.id,
            country_id=country.id,
            administrative_area_id=administrative_area.id,
            city=city,
            timezone=timezone,
            currency_code=currency_code
        )

        db.session.add(club)
        db.session.flush()

        new_user.club_id = club.id

        db.session.commit()

    except Exception as error:
        db.session.rollback()
        current_app.logger.exception(
            "No se pudo crear el cliente",
            exc_info=error
        )
        return error_response(
            "No pudimos crear el cliente. Intenta nuevamente.",
            "CLIENT_CREATION_FAILED",
            500
        )

    frontend_url = os.getenv(
        "FRONTEND_URL",
        "http://localhost:3000"
    ).rstrip("/")

    login_url = f"{frontend_url}/login"

    email_sent = True
    email_warning = None

    try:
        send_welcome_email(
            recipient_email=new_user.email,
            recipient_name=new_user.full_name,
            club_name=club.name,
            temporary_password=temp_password,
            login_url=login_url
        )

    except Exception as error:
        email_sent = False
        email_warning = (
            "El cliente fue creado, pero no se pudo enviar "
            "el correo de bienvenida."
        )

        current_app.logger.exception(
            "No se pudo enviar el correo de bienvenida "
            "al cliente %s",
            new_user.email,
            exc_info=error
        )

    return jsonify({
        "message": "Cliente creado exitosamente",
        "email_sent": email_sent,
        "email_warning": email_warning,
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

    clients = User.query.options(
        joinedload(User.club).joinedload(Club.sport),
        joinedload(User.club).joinedload(Club.country),
        joinedload(User.club).joinedload(Club.administrative_area)
    ).filter_by(role="club_owner") \
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
    RefreshToken.query.filter_by(
        user_id=client.id,
        revoked=False
    ).update({"revoked": True})
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


@api.route('/admin/clubs/<string:club_id>/suspend', methods=['PUT'])
@jwt_required()
def suspend_club(club_id):
    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para gestionar clubes",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    club.access_status = "suspended"

    club_user_ids = db.session.query(User.id).filter(
        User.club_id == club.id
    )

    RefreshToken.query.filter(
        RefreshToken.user_id.in_(club_user_ids),
        RefreshToken.revoked.is_(False)
    ).update(
        {"revoked": True},
        synchronize_session=False
    )

    db.session.commit()

    return jsonify({
        "message": "Acceso del club suspendido correctamente",
        "club": club.serialize()
    }), 200


@api.route('/admin/clubs/<string:club_id>/activate', methods=['PUT'])
@jwt_required()
def activate_club(club_id):
    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para gestionar clubes",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    was_suspended = club.access_status == "suspended"
    club.access_status = "active"

    if was_suspended:
        User.query.filter(
            User.club_id == club.id
        ).update(
            {User.session_version: User.session_version + 1},
            synchronize_session=False
        )

    db.session.commit()

    return jsonify({
        "message": "Acceso del club reactivado correctamente",
        "club": club.serialize()
    }), 200
