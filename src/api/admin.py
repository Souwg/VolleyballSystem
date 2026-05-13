import os
from flask import redirect, request
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from .models import db, User, Club, Team, Player, TeamPlayer, Attendance, TrainingSession, TrainingPlayer, MatchSession, MatchPlayer, MatchSubstitution, MatchEvent, PlayerMatchStat, TokenBlockedList, RefreshToken
import os
ENV = os.getenv("APP_ENV")

class SecureModelView(ModelView):

    def is_accessible(self):

        if ENV == "development":
            return True

        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = User.query.get(user_id)

            if user and user.role == "system_admin":
                return True

        except Exception:
            pass

        return False

    def inaccessible_callback(self, name, **kwargs):
        return redirect("/")


def setup_admin(app):
    app.secret_key = os.environ.get('FLASK_APP_KEY', 'sample key')
    app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

    admin = Admin(app, name='Volleyball System', url='/admin')

    admin.add_view(SecureModelView(User, db.session))
    admin.add_view(SecureModelView(Club, db.session))
    admin.add_view(SecureModelView(Team, db.session))
    admin.add_view(SecureModelView(Player, db.session))
    admin.add_view(SecureModelView(TeamPlayer, db.session))
    admin.add_view(SecureModelView(TrainingSession, db.session))
    admin.add_view(SecureModelView(TrainingPlayer, db.session))
    admin.add_view(SecureModelView(Attendance, db.session))
    admin.add_view(SecureModelView(MatchSession, db.session))
    admin.add_view(SecureModelView(MatchPlayer, db.session))
    admin.add_view(SecureModelView(MatchSubstitution, db.session))
    admin.add_view(SecureModelView(MatchEvent, db.session))
    admin.add_view(SecureModelView(PlayerMatchStat, db.session))
    admin.add_view(SecureModelView(TokenBlockedList, db.session))
    admin.add_view(SecureModelView(RefreshToken, db.session))
    