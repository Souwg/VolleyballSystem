import uuid
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean(), default=True)

    # 👇 B2B fields
    first_login = db.Column(db.Boolean(), default=True)
    role = db.Column(db.String(50), default="club_owner")
    subscription_status = db.Column(db.String(50), default="active")
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)
    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=True
    )

    club = db.relationship(
        "Club",
        backref=db.backref("users", lazy=True),
        foreign_keys=[club_id]
    )

    def __repr__(self):
        return f'<User {self.email}>'

    def serialize(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "first_login": self.first_login,
            "subscription_status": self.subscription_status,
            "created_at": self.created_at.isoformat()
        }

class Club(db.Model):
    __tablename__ = "clubs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(255))
    owner_id = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

    def __repr__(self):
        return f"<Club {self.name}>"

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat()
        }

class Team(db.Model):
    __tablename__ = "teams"

    __table_args__ = (
        db.UniqueConstraint("name", "club_id", name="unique_team_per_club"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    name = db.Column(db.String(120), nullable=False)  # Sub12, Sub10, Inicial, etc.

    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    club = db.relationship("Club", backref=db.backref("teams", lazy=True))

    def __repr__(self):
        return f"<Team {self.name}>"

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "club_id": self.club_id,
            "created_at": self.created_at.isoformat()
        }

class Player(db.Model):
    __tablename__ = "players"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    sex = db.Column(db.String(10))
    birth_date = db.Column(db.Date)

    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=False
    )

    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

    club = db.relationship(
        "Club",
        backref=db.backref("players", lazy=True)
    )

    def serialize(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "sex": self.sex,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "club_id": self.club_id,
            "created_at": self.created_at.isoformat()
        }
    
class TeamPlayer(db.Model):
    __tablename__ = "team_players"

    __table_args__ = (
        db.UniqueConstraint(
            "team_id",
            "player_id",
            name="unique_player_per_team"
        ),
        db.UniqueConstraint(
            "team_id",
            "player_number",
            name="unique_number_per_team"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    team_id = db.Column(
        db.String(36),
        db.ForeignKey("teams.id"),
        nullable=False
    )

    player_id = db.Column(
        db.String(36),
        db.ForeignKey("players.id"),
        nullable=False
    )

    player_number = db.Column(db.Integer, nullable=False)

    status = db.Column(
        db.String(20),
        default="active",
        nullable=False
    )

    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

    team = db.relationship(
        "Team",
        backref=db.backref("roster", lazy=True)
    )

    player = db.relationship(
        "Player",
        backref=db.backref("team_memberships", lazy=True)
    )

    def serialize(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "player_id": self.player_id,
            "player_number": self.player_number,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "player": self.player.serialize() if self.player else None
        }
    
class TrainingSession(db.Model):
    __tablename__ = "training_sessions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    team_id = db.Column(
        db.String(36),
        db.ForeignKey("teams.id"),
        nullable=False
    )

    date = db.Column(db.Date, nullable=False)

    start_time = db.Column(db.Time)

    end_time = db.Column(db.Time)

    location = db.Column(db.String(255))

    created_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id")
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship("Team", backref=db.backref("training_sessions", lazy=True))

    def serialize(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "date": self.date.isoformat() if self.date else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "location": self.location,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat()
        }
    
class TrainingPlayer(db.Model):
    __tablename__ = "training_players"

    __table_args__ = (
        db.UniqueConstraint(
            "training_id",
            "player_id",
            name="unique_player_per_training"
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    training_id = db.Column(
        db.String(36),
        db.ForeignKey("training_sessions.id"),
        nullable=False
    )

    player_id = db.Column(
        db.String(36),
        db.ForeignKey("players.id"),
        nullable=False
    )

    player_number = db.Column(db.Integer, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    training = db.relationship(
        "TrainingSession",
        backref=db.backref("roster_snapshot", lazy=True)
    )

    player = db.relationship(
        "Player",
        backref=db.backref("training_snapshots", lazy=True)
    )

    def serialize(self):
        return {
            "id": self.id,
            "training_id": self.training_id,
            "player_id": self.player_id,
            "player_number": self.player_number,
            "player": self.player.serialize() if self.player else None,
            "created_at": self.created_at.isoformat()
        }

class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    session_id = db.Column(
        db.String(36),
        db.ForeignKey("training_sessions.id"),
        nullable=False
    )

    player_id = db.Column(
        db.String(36),
        db.ForeignKey("players.id"),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="present"
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship(
        "TrainingSession",
        backref=db.backref("attendance", lazy=True)
    )

    player = db.relationship(
        "Player",
        backref=db.backref("attendance", lazy=True)
    )

    def serialize(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "player_id": self.player_id,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }
    
class TokenBlockedList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id"),
        nullable=False
    )

    jti = db.Column(db.String(36), nullable=False, unique=True)

    revoked = db.Column(db.Boolean, default=False)

    expires_at = db.Column(db.DateTime, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("refresh_tokens", lazy=True))