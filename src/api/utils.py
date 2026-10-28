from flask import jsonify, url_for
from flask_jwt_extended import get_jwt_identity
from src.api.models import User
import secrets
import string


class APIException(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)

def generate_sitemap(app):
    links = ['/admin/']
    for rule in app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if "GET" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            if "/admin/" not in url:
                links.append(url)

    links_html = "".join(["<li><a href='" + y + "'>" + y + "</a></li>" for y in links])
    return """
        <div style="text-align: center;">
        <img style="max-height: 80px" src='https://storage.googleapis.com/breathecode/boilerplates/rigo-baby.jpeg' />
        <h1>Rigo welcomes you to your API!!</h1>
        <p>API HOST: <script>document.write('<input style="padding: 5px; width: 300px" type="text" value="'+window.location.href+'" />');</script></p>
        <p>Start working on your project by following the <a href="https://start.4geeksacademy.com/starters/full-stack" target="_blank">Quick Start</a></p>
        <p>Remember to specify a real endpoint path like: </p>
        <ul style="text-align: left;">"""+links_html+"</ul></div>"

def get_current_user(*, allow_first_login=False):
    """
    Obtiene el usuario autenticado usando el JWT.
    Lanza una APIException si el usuario no existe.
    """

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        raise APIException(
            "Usuario no encontrado",
            status_code=404
        )

    if not user.is_active:
        raise APIException(
            "Tu cuenta está desactivada. Contacta al administrador.",
            status_code=403,
            payload={"error": True, "code": "ACCOUNT_DISABLED"}
        )

    ensure_club_access(user)

    if user.first_login is True and not allow_first_login:
        raise APIException(
            "Debes establecer tu nueva contraseña antes de continuar.",
            status_code=403,
            payload={"error": True, "code": "FIRST_LOGIN_REQUIRED"}
        )

    return user


def ensure_club_access(user):
    if user.role == "system_admin":
        return

    if user.club and user.club.access_status == "suspended":
        raise APIException(
            "El acceso a este club se encuentra suspendido.",
            status_code=403,
            payload={"error": True, "code": "CLUB_SUSPENDED"}
        )

def error_response(message, code, status):
    return jsonify({
        "error": True,
        "message": message,
        "code": code
    }), status

def generate_temp_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
