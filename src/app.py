import os
from dotenv import load_dotenv
from datetime import timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, get_jwt
from flask_cors import CORS
from src.api.extensions import bcrypt

load_dotenv()



from src.api.utils import APIException, generate_sitemap
from src.api.models import db, TokenBlockedList
from src.api.routes import api
from src.api.admin import setup_admin
from src.api.commands import setup_commands

# -------------------------------------------------------------------
# CREATE APP
# -------------------------------------------------------------------

ENV = os.getenv("APP_ENV", "production")
static_file_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../public/')

app = Flask(__name__)
app.url_map.strict_slashes = False

bcrypt.init_app(app)  
# -------------------------------------------------------------------
# CORS — THIS FIXES YOUR ERROR
# -------------------------------------------------------------------
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# -------------------------------------------------------------------
# JWT CONFIG
# -------------------------------------------------------------------
app.config["JWT_SECRET_KEY"] = (
    os.getenv("TOKEN_SECRET")
    or os.getenv("FLASK_APP_KEY")
    or "dev-secret-local"
)
# Access corto (seguro)
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)

# Refresh largo (sesión real SaaS)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=7)

# Usaremos headers (como ya trabajas)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]

# Necesario para distinguir tipos de token
app.config["JWT_ALGORITHM"] = "HS256"
jwt = JWTManager(app)

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload: dict) -> bool:
    jti = jwt_payload["jti"]
    token = TokenBlockedList.query.filter_by(jti=jti).first()
    return token is not None

# -------------------------------------------------------------------
# DATABASE
# -------------------------------------------------------------------
db_url = os.getenv("DATABASE_URL")

if db_url is not None:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace("postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/test.db"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

MIGRATE = Migrate(app, db, compare_type=True)
db.init_app(app)

# -------------------------------------------------------------------
# BLUEPRINTS & ADMIN
# -------------------------------------------------------------------

#habilitar Flask-Admin en desarrollo
if ENV == "development":
    setup_admin(app)

setup_commands(app)
app.register_blueprint(api, url_prefix='/api')

# -------------------------------------------------------------------
# ERROR HANDLER
# -------------------------------------------------------------------
@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code

# -------------------------------------------------------------------
# GLOBAL EXCEPTION HANDLER (Production Safety Net)
# -------------------------------------------------------------------
@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """
    Captura cualquier excepción no controlada y mantiene
    el contrato JSON del API. Evita respuestas HTML 500.
    """

    # Muy importante: si algo falló en medio de una transacción
    db.session.rollback()

    # Log interno (para que en consola / docker logs sí veas el error real)
    app.logger.exception("Unhandled exception:", exc_info=error)

    return jsonify({
        "error": True,
        "message": "Ocurrió un error interno",
        "code": "INTERNAL_ERROR"
    }), 500

# -------------------------------------------------------------------
# SITEMAP & STATIC
# -------------------------------------------------------------------
@app.route('/')
def sitemap():
    if ENV == "development":
        return generate_sitemap(app)
    return send_from_directory(static_file_dir, 'index.html')

@app.route('/<path:path>', methods=['GET'])
def serve_any_other_file(path):
    if not os.path.isfile(os.path.join(static_file_dir, path)):
        path = 'index.html'
    response = send_from_directory(static_file_dir, path)
    response.cache_control.max_age = 0
    return response

# -------------------------------------------------------------------
# RUN
# -------------------------------------------------------------------
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3005))
    app.run(host='0.0.0.0', port=PORT, debug=True)