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
        db.UniqueConstraint(
            "name",
            "gender",
            "club_id",
            name="unique_team_gender_per_club"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    name = db.Column(db.String(120), nullable=False)  
    gender = db.Column(db.String(20), nullable=False, default="female") 

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
            "gender": self.gender,
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

class MatchSession(db.Model):
    __tablename__ = "match_sessions"

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    team_id = db.Column(
        db.String(36),
        db.ForeignKey("teams.id"),
        nullable=False
    )

    date = db.Column(db.Date, nullable=False)

    opponent_name = db.Column(db.String(120))

    match_type = db.Column(
        db.String(30),
        default="official"
    )

    location = db.Column(db.String(255))

    notes = db.Column(db.Text)

    created_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id")
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    team = db.relationship(
        "Team",
        backref=db.backref("match_sessions", lazy=True)
    )

    def serialize(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "date": self.date.isoformat() if self.date else None,
            "opponent_name": self.opponent_name,
            "match_type": self.match_type,
            "location": self.location,
            "notes": self.notes,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat()
        }
    
class MatchPlayer(db.Model):
    __tablename__ = "match_players"

    __table_args__ = (
        db.UniqueConstraint(
            "match_id",
            "player_id",
            name="unique_player_per_match"
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    match_id = db.Column(
        db.String(36),
        db.ForeignKey("match_sessions.id"),
        nullable=False
    )

    player_id = db.Column(
        db.String(36),
        db.ForeignKey("players.id"),
        nullable=False
    )

    player_number = db.Column(db.Integer, nullable=False)

    attendance_status = db.Column(
        db.String(20),
        default="present"
    )

    did_play = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    match = db.relationship(
        "MatchSession",
        backref=db.backref("roster_snapshot", lazy=True)
    )

    player = db.relationship(
        "Player",
        backref=db.backref("match_snapshots", lazy=True)
    )

    def serialize(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "player_id": self.player_id,
            "player_number": self.player_number,
            "attendance_status": self.attendance_status,
            "did_play": self.did_play,
            "created_at": self.created_at.isoformat(),
            "player": self.player.serialize() if self.player else None
        }
    
class PlayerMatchStat(db.Model):
    __tablename__ = "player_match_stats"

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    match_player_id = db.Column(
        db.String(36),
        db.ForeignKey("match_players.id"),
        nullable=False,
        unique=True
    )

    position = db.Column(db.String(10))

    attacks_total = db.Column(db.Integer, default=0)
    attacks_positive = db.Column(db.Integer, default=0)
    attacks_errors = db.Column(db.Integer, default=0)

    receptions_total = db.Column(db.Integer, default=0)
    receptions_positive = db.Column(db.Integer, default=0)
    receptions_negative = db.Column(db.Integer, default=0)

    serves_total = db.Column(db.Integer, default=0)
    serves_aces = db.Column(db.Integer, default=0)
    serves_errors = db.Column(db.Integer, default=0)

    blocks_total = db.Column(db.Integer, default=0)
    blocks_points = db.Column(db.Integer, default=0)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    match_player = db.relationship(
        "MatchPlayer",
        backref=db.backref("performance_stats", uselist=False)
    )

    def serialize(self):
        return {
            "id": self.id,
            "match_player_id": self.match_player_id,
            "position": self.position,
            "attacks_total": self.attacks_total,
            "attacks_positive": self.attacks_positive,
            "attacks_errors": self.attacks_errors,
            "receptions_total": self.receptions_total,
            "receptions_positive": self.receptions_positive,
            "receptions_negative": self.receptions_negative,
            "serves_total": self.serves_total,
            "serves_aces": self.serves_aces,
            "serves_errors": self.serves_errors,
            "blocks_total": self.blocks_total,
            "blocks_points": self.blocks_points,
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