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
            "club_id": self.club_id,
            "club": self.club.serialize() if self.club else None,
            "created_at": self.created_at.isoformat()
            }

class Club(db.Model):
    __tablename__ = "clubs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(120), nullable=True)
    state = db.Column(db.String(120), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    primary_color = db.Column(db.String(20), nullable=True)
    secondary_color = db.Column(db.String(20), nullable=True)
    owner_id = db.Column(db.String(36), nullable=False)
    default_enrollment_fee = db.Column(db.Float, nullable=True)
    default_monthly_fee = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)
    

    def __repr__(self):
        return f"<Club {self.name}>"

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "state": self.state,
            "image_url": self.image_url,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "owner_id": self.owner_id,
            "default_enrollment_fee": self.default_enrollment_fee,
            "default_monthly_fee": self.default_monthly_fee,
            "created_at": self.created_at.isoformat()
        }

class Category(db.Model):
    __tablename__ = "categories"

    __table_args__ = (
        db.UniqueConstraint(
            "name",
            "club_id",
            name="unique_category_per_club"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    name = db.Column(db.String(120), nullable=False)

    description = db.Column(db.String(255), nullable=True)

    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    club = db.relationship(
        "Club",
        backref=db.backref("categories", lazy=True)
    )

    def __repr__(self):
        return f"<Category {self.name}>"

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "club_id": self.club_id,
            "created_at": self.created_at.isoformat()
        }

class Team(db.Model):
    __tablename__ = "teams"

    __table_args__ = (
        db.UniqueConstraint(
            "name",
            "gender",
            "category_id",
            "club_id",
            name="unique_team_gender_per_category"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    name = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(20), nullable=False, default="female")

    category_id = db.Column(
        db.String(36),
        db.ForeignKey("categories.id"),
        nullable=False
    )

    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship(
        "Category",
        backref=db.backref("teams", lazy=True)
    )

    club = db.relationship(
        "Club",
        backref=db.backref("teams", lazy=True)
    )

    def __repr__(self):
        return f"<Team {self.name}>"

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "category_id": self.category_id,
            "category": self.category.serialize() if self.category else None,
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
    main_position = db.Column(db.String(20), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    representative_name = db.Column(db.String(120), nullable=True)
    representative_phone = db.Column(db.String(30), nullable=True)
    enrollment_date = db.Column(db.Date, nullable=True)
    enrollment_fee = db.Column(db.Float, nullable=True)
    monthly_fee = db.Column(db.Float, nullable=True)
    payment_cycle_day = db.Column(db.Integer, nullable=True)

    is_active = db.Column(db.Boolean(), default=True, nullable=False)

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
            "main_position": self.main_position,
            "image_url": self.image_url,
            "representative_name": self.representative_name,
            "representative_phone": self.representative_phone,
            "enrollment_date": self.enrollment_date.isoformat() if self.enrollment_date else None,
            "enrollment_fee": self.enrollment_fee,
            "monthly_fee": self.monthly_fee,
            "payment_cycle_day": self.payment_cycle_day,
            "is_active": self.is_active,
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
        default="official", nullable=False
    )

    location = db.Column(db.String(255))
    home_sets = db.Column(db.Integer, default=0, nullable=False)
    opponent_sets = db.Column(db.Integer, default=0, nullable=False)
    result = db.Column(db.String(20))
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    match_step = db.Column(db.Integer, default=0, nullable=False)

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
            "home_sets": self.home_sets,
            "opponent_sets": self.opponent_sets,
            "result": self.result,
            "match_step": self.match_step,
            "is_completed": self.is_completed,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
           
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

    is_called = db.Column(db.Boolean, default=False, nullable=False)

    attendance_status = db.Column(
        db.String(20),
        nullable=True,
    )

    did_play = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    is_on_court = db.Column(db.Boolean(), default=False)

    position = db.Column(db.String(20), nullable=True)

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
            "is_called": self.is_called,
            "attendance_status": self.attendance_status,
            "did_play": self.did_play,
            "is_on_court": self.is_on_court,
            "position": self.position,
            "created_at": self.created_at.isoformat(),
            "player": self.player.serialize() if self.player else None
        }
class MatchSubstitution(db.Model):
    __tablename__ = "match_substitutions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    match_id = db.Column(db.String(36), db.ForeignKey("match_sessions.id"), nullable=False)
    set_number = db.Column(db.Integer, nullable=False)

    player_out_id = db.Column(db.String(36), db.ForeignKey("match_players.id"), nullable=False)
    player_in_id = db.Column(db.String(36), db.ForeignKey("match_players.id"), nullable=False)

    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

    match = db.relationship("MatchSession", backref="substitutions")
    player_out = db.relationship(
        "MatchPlayer",
        foreign_keys=[player_out_id]
    )
    player_in = db.relationship(
        "MatchPlayer",
        foreign_keys=[player_in_id]
    )

    def serialize(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "set_number": self.set_number,
            "player_out_id": self.player_out_id,
            "player_in_id": self.player_in_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
class MatchEvent(db.Model):
    __tablename__ = "match_events"

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

    match_player_id = db.Column(
        db.String(36),
        db.ForeignKey("match_players.id"),
        nullable=False
    )

    action_type = db.Column(
        db.String(30),
        nullable=False
    )
    # attack, reception, defense, set, serve, block

    result = db.Column(
        db.String(30),
        nullable=False
    )

    set_number = db.Column(db.Integer, nullable=False, default=1)
    # positive, neutral, negative, error, ace, in, point

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    match = db.relationship(
        "MatchSession",
        backref=db.backref("events", lazy=True)
    )

    match_player = db.relationship(
        "MatchPlayer",
        backref=db.backref("events", lazy=True)
    )

    def serialize(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "match_player_id": self.match_player_id,
            "action_type": self.action_type,
            "result": self.result,
            "set_number": self.set_number,
            "created_at": self.created_at.isoformat()
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



    attacks_total = db.Column(db.Integer, default=0)
    attacks_positive = db.Column(db.Integer, default=0)
    attacks_neutral = db.Column(db.Integer, default=0)
    attacks_errors = db.Column(db.Integer, default=0)

    receptions_total = db.Column(db.Integer, default=0)
    receptions_positive = db.Column(db.Integer, default=0)
    receptions_neutral = db.Column(db.Integer, default=0)
    receptions_negative = db.Column(db.Integer, default=0)

    defenses_total = db.Column(db.Integer, default=0)
    defenses_positive = db.Column(db.Integer, default=0)
    defenses_neutral = db.Column(db.Integer, default=0)
    defenses_negative = db.Column(db.Integer, default=0)

    sets_total = db.Column(db.Integer, default=0)
    sets_positive = db.Column(db.Integer, default=0)
    sets_neutral = db.Column(db.Integer, default=0)
    sets_errors = db.Column(db.Integer, default=0)

    serves_total = db.Column(db.Integer, default=0)
    serves_in = db.Column(db.Integer, default=0)
    serves_aces = db.Column(db.Integer, default=0)
    serves_errors = db.Column(db.Integer, default=0)

    
    blocks_total = db.Column(db.Integer, nullable=False, default=0)
    blocks_points = db.Column(db.Integer, default=0)
    blocks_neutral = db.Column(db.Integer, nullable=False, default=0)
    blocks_errors = db.Column(db.Integer, nullable=False, default=0)

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
            "attacks_total": self.attacks_total,
            "attacks_positive": self.attacks_positive,
            "attacks_neutral": self.attacks_neutral,
            "attacks_errors": self.attacks_errors,
            "receptions_total": self.receptions_total,
            "receptions_positive": self.receptions_positive,
            "receptions_neutral": self.receptions_neutral,
            "receptions_negative": self.receptions_negative,
            "defenses_total": self.defenses_total,
            "defenses_positive": self.defenses_positive,
            "defenses_neutral": self.defenses_neutral,
            "defenses_negative": self.defenses_negative,
            "sets_total": self.sets_total,
            "sets_positive": self.sets_positive,
            "sets_neutral": self.sets_neutral,
            "sets_errors": self.sets_errors,
            "serves_total": self.serves_total,
            "serves_in": self.serves_in,
            "serves_aces": self.serves_aces,
            "serves_errors": self.serves_errors,
            "blocks_total": self.blocks_total,
            "blocks_points": self.blocks_points,
            "blocks_neutral": self.blocks_neutral,
            "blocks_errors": self.blocks_errors,
            "created_at": self.created_at.isoformat()
        }
    
class PlayerPayment(db.Model):
    __tablename__ = "player_payments"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    club_id = db.Column(db.String(36), db.ForeignKey("clubs.id"), nullable=False)
    player_id = db.Column(db.String(36), db.ForeignKey("players.id"), nullable=False)

    payment_type = db.Column(db.String(30), nullable=False, default="monthly")
    # enrollment, monthly, uniform, tournament, extra

    amount = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(20), default="pending", nullable=False)

    period_start = db.Column(db.Date, nullable=True)
    period_end = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)

    payment_date = db.Column(db.Date, nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)
    reference = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    paid_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

    player = db.relationship("Player", backref=db.backref("payments", lazy=True))
    club = db.relationship("Club", backref=db.backref("payments", lazy=True))

    def serialize(self):
        return {
            "id": self.id,
            "club_id": self.club_id,
            "player_id": self.player_id,
            "payment_type": self.payment_type,
            "amount": self.amount,
            "status": self.status,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "payment_method": self.payment_method,
            "reference": self.reference,
            "receipt": self.receipt.serialize() if self.receipt else None,
            "notes": self.notes,
            "created_by": self.created_by,
            "paid_by": self.paid_by,
            "created_at": self.created_at.isoformat(),
            "player": self.player.serialize() if self.player else None
        }
    
class PaymentReceipt(db.Model):
    __tablename__ = "payment_receipts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    payment_id = db.Column(
        db.String(36),
        db.ForeignKey("player_payments.id"),
        nullable=False,
        unique=True
    )

    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=False
    )

    player_id = db.Column(
        db.String(36),
        db.ForeignKey("players.id"),
        nullable=False
    )

    receipt_number = db.Column(db.String(40), nullable=False, unique=True)

    pdf_url = db.Column(db.String(500), nullable=True)

    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

    sent_at = db.Column(db.DateTime, nullable=True)
    sent_channel = db.Column(db.String(30), nullable=True)
    sent_to = db.Column(db.String(120), nullable=True)

    payment = db.relationship(
        "PlayerPayment",
        backref=db.backref(
            "receipt",
            uselist=False,
            cascade="all, delete-orphan",
            single_parent=True
        )
    )

    def serialize(self):
        return {
            "id": self.id,
            "payment_id": self.payment_id,
            "club_id": self.club_id,
            "player_id": self.player_id,
            "receipt_number": self.receipt_number,
            "pdf_url": self.pdf_url,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "sent_channel": self.sent_channel,
            "sent_to": self.sent_to,
        }
    
class ReceiptCounter(db.Model):
    __tablename__ = "receipt_counters"

    __table_args__ = (
        db.UniqueConstraint(
            "club_id",
            "year",
            name="unique_receipt_counter_per_club_year"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=False
    )

    year = db.Column(db.Integer, nullable=False)

    next_sequence = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    club = db.relationship(
        "Club",
        backref=db.backref("receipt_counters", lazy=True)
    )

    def serialize(self):
        return {
            "id": self.id,
            "club_id": self.club_id,
            "year": self.year,
            "next_sequence": self.next_sequence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
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