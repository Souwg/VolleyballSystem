import uuid
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from src.api.currency_registry import get_currency_definition

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean(), default=True)
    session_version = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

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


class Sport(db.Model):
    __tablename__ = "sports"

    __table_args__ = (
        db.UniqueConstraint(
            "code",
            name="uq_sports_code"
        ),
        db.CheckConstraint(
            "code = UPPER(code)",
            name="ck_sports_code_uppercase"
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    code = db.Column(db.String(30), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    is_active = db.Column(
        db.Boolean(),
        nullable=False,
        default=False,
        server_default=db.false()
    )
    clubs = db.relationship(
        "Club",
        back_populates="sport",
        lazy=True
    )

    def serialize(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "is_active": self.is_active
        }


class Country(db.Model):
    __tablename__ = "countries"

    __table_args__ = (
        db.UniqueConstraint("code", name="uq_countries_code"),
        db.CheckConstraint(
            "code = UPPER(code)",
            name="ck_countries_code_uppercase"
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    code = db.Column(db.String(2), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    is_active = db.Column(
        db.Boolean(),
        nullable=False,
        default=False,
        server_default=db.false()
    )

    areas = db.relationship(
        "AdministrativeArea",
        back_populates="country",
        lazy=True
    )
    clubs = db.relationship(
        "Club",
        back_populates="country",
        lazy=True
    )

    def serialize(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "is_active": self.is_active
        }


class AdministrativeArea(db.Model):
    __tablename__ = "administrative_areas"

    __table_args__ = (
        db.UniqueConstraint(
            "country_id",
            "code",
            name="uq_administrative_areas_country_code"
        ),
        db.CheckConstraint(
            "code = UPPER(code)",
            name="ck_administrative_areas_code_uppercase"
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    country_id = db.Column(
        db.String(36),
        db.ForeignKey("countries.id"),
        nullable=False
    )
    code = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(
        db.Boolean(),
        nullable=False,
        default=False,
        server_default=db.false()
    )

    country = db.relationship(
        "Country",
        back_populates="areas"
    )
    clubs = db.relationship(
        "Club",
        back_populates="administrative_area",
        lazy=True
    )

    def serialize(self):
        return {
            "id": self.id,
            "country_id": self.country_id,
            "code": self.code,
            "name": self.name,
            "is_active": self.is_active
        }


class Club(db.Model):
    __tablename__ = "clubs"

    __table_args__ = (
        db.CheckConstraint(
            "access_status IN ('active', 'suspended')",
            name="ck_clubs_access_status"
        ),
        db.CheckConstraint(
            "LENGTH(currency_code) = 3 AND currency_code = UPPER(currency_code)",
            name="ck_clubs_currency_code_format"
        ),
    )

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
    currency_code = db.Column(db.String(3), nullable=False)
    sport_id = db.Column(
        db.String(36),
        db.ForeignKey("sports.id"),
        nullable=False
    )
    country_id = db.Column(
        db.String(36),
        db.ForeignKey("countries.id"),
        nullable=True
    )
    administrative_area_id = db.Column(
        db.String(36),
        db.ForeignKey("administrative_areas.id"),
        nullable=True
    )
    city = db.Column(db.String(120), nullable=True)
    timezone = db.Column(db.String(120), nullable=False)
    access_status = db.Column(
        db.String(20),
        nullable=False,
        default="active",
        server_default="active"
    )
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

    sport = db.relationship(
        "Sport",
        back_populates="clubs"
    )
    country = db.relationship(
        "Country",
        back_populates="clubs"
    )
    administrative_area = db.relationship(
        "AdministrativeArea",
        back_populates="clubs"
    )
    seasons = db.relationship(
        "Season",
        back_populates="club",
        lazy=True
    )
    

    def __repr__(self):
        return f"<Club {self.name}>"

    def serialize(self):
        currency = get_currency_definition(self.currency_code)

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
            "currency_code": self.currency_code,
            "currency": currency.serialize() if currency else None,
            "sport_id": self.sport_id,
            "sport": (
                {
                    "id": self.sport.id,
                    "code": self.sport.code,
                    "name": self.sport.name
                }
                if self.sport
                else None
            ),
            "country_id": self.country_id,
            "country": (
                {
                    "id": self.country.id,
                    "code": self.country.code,
                    "name": self.country.name
                }
                if self.country
                else None
            ),
            "administrative_area_id": self.administrative_area_id,
            "administrative_area": (
                {
                    "id": self.administrative_area.id,
                    "code": self.administrative_area.code,
                    "name": self.administrative_area.name
                }
                if self.administrative_area
                else None
            ),
            "city": self.city,
            "timezone": self.timezone,
            "access_status": self.access_status,
            "created_at": self.created_at.isoformat()
        }


class Season(db.Model):
    __tablename__ = "seasons"

    __table_args__ = (
        db.UniqueConstraint(
            "id",
            "club_id",
            name="uq_seasons_id_club_id"
        ),
        db.CheckConstraint(
            "status IN ('planned', 'active', 'closed')",
            name="ck_seasons_status"
        ),
        db.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_seasons_date_range"
        ),
        db.Index(
            "uq_seasons_active_per_club",
            "club_id",
            unique=True,
            postgresql_where=db.text("status = 'active'"),
            sqlite_where=db.text("status = 'active'")
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=False
    )
    name = db.Column(db.String(120), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="active",
        server_default="active"
    )
    created_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id"),
        nullable=True
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    club = db.relationship(
        "Club",
        back_populates="seasons"
    )
    creator = db.relationship(
        "User",
        foreign_keys=[created_by],
        backref=db.backref("seasons_created", lazy=True)
    )

    def serialize(self):
        return {
            "id": self.id,
            "club_id": self.club_id,
            "name": self.name,
            "start_date": (
                self.start_date.isoformat()
                if self.start_date
                else None
            ),
            "end_date": (
                self.end_date.isoformat()
                if self.end_date
                else None
            ),
            "status": self.status,
            "created_by": self.created_by,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            )
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
        db.ForeignKeyConstraint(
            ["season_id", "club_id"],
            ["seasons.id", "seasons.club_id"],
            name="fk_teams_season_club"
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

    season_id = db.Column(
        db.String(36),
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship(
        "Category",
        backref=db.backref("teams", lazy=True)
    )

    club = db.relationship(
        "Club",
        backref=db.backref("teams", lazy=True),
        foreign_keys=[club_id],
        overlaps="season,teams"
    )

    season = db.relationship(
        "Season",
        backref=db.backref(
            "teams",
            lazy=True,
            overlaps="club,teams"
        ),
        foreign_keys=[season_id, club_id],
        overlaps="club,teams"
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
            "season_id": self.season_id,
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
    payment_control_start_date = db.Column(db.Date, nullable=True)

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
            "payment_control_start_date": (
                self.payment_control_start_date.isoformat()
                if self.payment_control_start_date
                else None
            ),
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
    
class Tournament(db.Model):
    __tablename__ = "tournaments"

    __table_args__ = (
        db.UniqueConstraint(
            "club_id",
            "name",
            "start_date",
            name="unique_tournament_per_club"
        ),
        db.ForeignKeyConstraint(
            ["season_id", "club_id"],
            ["seasons.id", "seasons.club_id"],
            name="fk_tournaments_season_club"
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=False
    )

    season_id = db.Column(
        db.String(36),
        nullable=False
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    organizer_name = db.Column(
        db.String(150),
        nullable=True
    )

    start_date = db.Column(
        db.Date,
        nullable=False
    )

    end_date = db.Column(
        db.Date,
        nullable=True
    )

    default_referee_fee = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="active"
    )

    created_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    club = db.relationship(
        "Club",
        backref=db.backref(
            "tournaments",
            lazy=True
        ),
        foreign_keys=[club_id],
        overlaps="season,tournaments"
    )

    season = db.relationship(
        "Season",
        backref=db.backref(
            "tournaments",
            lazy=True,
            overlaps="club,tournaments"
        ),
        foreign_keys=[season_id, club_id],
        overlaps="club,tournaments"
    )

    creator = db.relationship(
        "User",
        foreign_keys=[created_by],
        backref=db.backref(
            "tournaments_created",
            lazy=True
        )
    )

    def serialize(self):
        return {
            "id": self.id,
            "club_id": self.club_id,
            "season_id": self.season_id,
            "name": self.name,
            "organizer_name": self.organizer_name,
            "start_date": (
                self.start_date.isoformat()
                if self.start_date
                else None
            ),
            "end_date": (
                self.end_date.isoformat()
                if self.end_date
                else None
            ),
            "default_referee_fee": (
                float(self.default_referee_fee)
                if self.default_referee_fee is not None
                else 0
            ),
            "currency_code": (
                self.club.currency_code
                if self.club
                else None
            ),
            "status": self.status,
            "created_by": self.created_by,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            )
        }


class TournamentTeam(db.Model):
    __tablename__ = "tournament_teams"

    __table_args__ = (
        db.UniqueConstraint(
            "tournament_id",
            "team_id",
            name="unique_team_per_tournament"
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    tournament_id = db.Column(
        db.String(36),
        db.ForeignKey("tournaments.id"),
        nullable=False
    )

    team_id = db.Column(
        db.String(36),
        db.ForeignKey("teams.id"),
        nullable=False
    )

    registration_fee = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="active"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    tournament = db.relationship(
        "Tournament",
        backref=db.backref(
            "team_entries",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    team = db.relationship(
        "Team",
        backref=db.backref(
            "tournament_entries",
            lazy=True
        )
    )

    def serialize(self):
        return {
            "id": self.id,
            "tournament_id": self.tournament_id,
            "tournament": (
                {
                    "id": self.tournament.id,
                    "name": self.tournament.name,
                    "organizer_name": self.tournament.organizer_name,
                    "start_date": (
                        self.tournament.start_date.isoformat()
                        if self.tournament.start_date
                        else None
                    ),
                    "end_date": (
                        self.tournament.end_date.isoformat()
                        if self.tournament.end_date
                        else None
                    ),
                    "default_referee_fee": (
                        float(self.tournament.default_referee_fee)
                        if self.tournament.default_referee_fee is not None
                        else 0
                    ),
                    "currency_code": (
                        self.tournament.club.currency_code
                        if self.tournament.club
                        else None
                    ),
                    "status": self.tournament.status,
                }
                if self.tournament
                else None
            ),
            "team_id": self.team_id,
            "registration_fee": (
                float(self.registration_fee)
                if self.registration_fee is not None
                else 0
            ),
            "currency_code": (
                self.tournament.club.currency_code
                if self.tournament and self.tournament.club
                else None
            ),
            "status": self.status,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            "team": (
                self.team.serialize()
                if self.team
                else None
            )
        }


class TournamentPlayer(db.Model):
    __tablename__ = "tournament_players"

    __table_args__ = (
        db.UniqueConstraint(
            "tournament_team_id",
            "player_id",
            name="unique_player_per_tournament_team"
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    tournament_team_id = db.Column(
        db.String(36),
        db.ForeignKey("tournament_teams.id"),
        nullable=False
    )

    player_id = db.Column(
        db.String(36),
        db.ForeignKey("players.id"),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="active"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    tournament_team = db.relationship(
        "TournamentTeam",
        backref=db.backref(
            "registered_players",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    player = db.relationship(
        "Player",
        backref=db.backref(
            "tournament_registrations",
            lazy=True
        )
    )

    def serialize(self):
        return {
            "id": self.id,
            "tournament_team_id": self.tournament_team_id,
            "player_id": self.player_id,
            "status": self.status,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            "player": (
                self.player.serialize()
                if self.player
                else None
            )
        }
    
class TrainingSession(db.Model):
    __tablename__ = "training_sessions"

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_training_sessions_status"
        ),
    )

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

    status = db.Column(
        db.String(20),
        nullable=False,
        default="scheduled",
        server_default="scheduled"
    )

    created_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id")
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship("Team", backref=db.backref("training_sessions", lazy=True))
    audit_events = db.relationship(
        "TrainingAuditEvent",
        back_populates="training",
        order_by=lambda: (
            TrainingAuditEvent.created_at.desc(),
            TrainingAuditEvent.id.desc()
        )
    )

    def serialize(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "date": self.date.isoformat() if self.date else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "location": self.location,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat()
        }


class TrainingAuditEvent(db.Model):
    """Registro inmutable de correcciones históricas de entrenamientos."""

    __tablename__ = "training_audit_events"

    __table_args__ = (
        db.CheckConstraint(
            "action IN ("
            "'training_metadata_corrected', "
            "'training_attendance_corrected', "
            "'training_reactivated'"
            ")",
            name="ck_training_audit_events_action"
        ),
        db.Index(
            "ix_training_audit_events_training_created_at",
            "training_id",
            "created_at"
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
    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=False
    )
    action = db.Column(db.String(50), nullable=False)
    changes_json = db.Column(db.JSON, nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    created_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id"),
        nullable=False
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    training = db.relationship(
        "TrainingSession",
        back_populates="audit_events"
    )
    creator = db.relationship(
        "User",
        foreign_keys=[created_by],
        backref=db.backref("training_audit_events_created", lazy=True)
    )

    def serialize(self):
        return {
            "id": self.id,
            "training_id": self.training_id,
            "action": self.action,
            "changes": self.changes_json,
            "reason": self.reason,
            "created_by": self.created_by,
            "created_by_name": (
                self.creator.full_name
                if self.creator
                else None
            ),
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            )
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

    __table_args__ = (
        db.CheckConstraint(
            "capture_mode IS NULL OR capture_mode IN ('live', 'summary')",
            name="ck_match_sessions_capture_mode"
        ),
    )

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

    tournament_team_id = db.Column(
        db.String(36),
        db.ForeignKey("tournament_teams.id"),
        nullable=True
    )

    referee_fee = db.Column(
        db.Numeric(10, 2),
        nullable=True
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
    capture_mode = db.Column(db.String(20), nullable=True)

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

    tournament_team = db.relationship(
        "TournamentTeam",
        backref=db.backref(
            "match_sessions",
            lazy=True
        )
    )

    def serialize(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "tournament_team_id": self.tournament_team_id,
            "referee_fee": (
                float(self.referee_fee)
                if self.referee_fee is not None
                else None
            ),
            "currency_code": (
                self.team.club.currency_code
                if self.team and self.team.club
                else None
            ),
            "tournament_team": (
                self.tournament_team.serialize()
                if self.tournament_team
                else None
            ),
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
            "capture_mode": self.capture_mode,
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
    __table_args__ = (
        db.Index(
            "uq_player_payments_monthly_cycle",
            "club_id",
            "player_id",
            "period_start",
            unique=True,
            postgresql_where=db.text("payment_type = 'monthly'"),
            sqlite_where=db.text("payment_type = 'monthly'")
        ),
        db.Index(
            "uq_player_payments_tournament_charge",
            "club_id",
            "player_id",
            "tournament_team_id",
            unique=True,
            postgresql_where=db.text("payment_type = 'tournament'"),
            sqlite_where=db.text("payment_type = 'tournament'")
        ),
        db.Index(
            "uq_player_payments_referee_charge",
            "club_id",
            "player_id",
            "match_id",
            unique=True,
            postgresql_where=db.text("payment_type = 'referee'"),
            sqlite_where=db.text("payment_type = 'referee'")
        ),
        db.CheckConstraint(
            "LENGTH(currency_code) = 3 "
            "AND currency_code = UPPER(currency_code)",
            name="ck_player_payments_currency_code_format"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    club_id = db.Column(db.String(36), db.ForeignKey("clubs.id"), nullable=False)
    player_id = db.Column(db.String(36), db.ForeignKey("players.id"), nullable=False)

    tournament_team_id = db.Column(
        db.String(36),
        db.ForeignKey("tournament_teams.id"),
        nullable=True
    )

    match_id = db.Column(
        db.String(36),
        db.ForeignKey("match_sessions.id"),
        nullable=True
    )

    payment_type = db.Column(db.String(30), nullable=False, default="monthly")
    
    # enrollment, monthly, uniform, tournament, referee, extra
    amount = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0
    )
    currency_code = db.Column(db.String(3), nullable=False)
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
    settlement_source = db.Column(db.String(20), nullable=True)

    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

    player = db.relationship("Player", backref=db.backref("payments", lazy=True))
    club = db.relationship("Club", backref=db.backref("payments", lazy=True))

    tournament_team = db.relationship(
        "TournamentTeam",
        backref=db.backref(
            "payments",
            lazy=True
        )
    )

    match = db.relationship(
        "MatchSession",
        backref=db.backref(
            "payments",
            lazy=True
        )
    )

    receipts = db.relationship(
        "PaymentReceipt",
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="PaymentReceipt.generated_at"
    )

    @property
    def active_receipt(self):
        return next(
            (
                receipt
                for receipt in self.receipts
                if receipt.status == "issued"
            ),
            None
        )

    @property
    def has_receipt_history(self):
        return bool(self.receipts)

    @property
    def receipt(self):
        """Compatibilidad del API: expone únicamente el recibo vigente."""
        return self.active_receipt

    def serialize(self):
        return {
            "id": self.id,
            "club_id": self.club_id,
            "player_id": self.player_id,
            "tournament_team_id": self.tournament_team_id,
            "match_id": self.match_id,
            "payment_type": self.payment_type,
            "amount": (
                float(self.amount)
                if self.amount is not None
                else 0
            ),
            "currency_code": self.currency_code,
            "status": self.status,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "payment_method": self.payment_method,
            "reference": self.reference,
            "settlement_source": self.settlement_source,
            "receipt": (
                self.active_receipt.serialize()
                if self.active_receipt
                else None
            ),
            "notes": self.notes,
            "created_by": self.created_by,
            "paid_by": self.paid_by,
            "created_at": self.created_at.isoformat(),
            "player": self.player.serialize() if self.player else None,
            "tournament_team": (
                self.tournament_team.serialize()
                if self.tournament_team
                else None
            ),
            "match": (
                {
                    "id": self.match.id,
                    "date": (
                        self.match.date.isoformat()
                        if self.match.date
                        else None
                    ),
                    "opponent_name": self.match.opponent_name,
                    "team_id": self.match.team_id,
                }
                if self.match
                else None
            ),
        }
    
class PaymentReceipt(db.Model):
    __tablename__ = "payment_receipts"

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('issued', 'invalidated')",
            name="ck_payment_receipts_status"
        ),
        db.CheckConstraint(
            "snapshot_source IN ('issued', 'legacy_backfill')",
            name="ck_payment_receipts_snapshot_source"
        ),
        db.CheckConstraint(
            "LENGTH(currency_code_snapshot) = 3 "
            "AND currency_code_snapshot = UPPER(currency_code_snapshot)",
            name="ck_payment_receipts_currency_code_snapshot_format"
        ),
        db.Index(
            "uq_payment_receipts_issued_payment",
            "payment_id",
            unique=True,
            postgresql_where=db.text("status = 'issued'"),
            sqlite_where=db.text("status = 'issued'")
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    payment_id = db.Column(
        db.String(36),
        db.ForeignKey("player_payments.id"),
        nullable=False
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

    status = db.Column(
        db.String(20),
        nullable=False,
        default="issued",
        server_default="issued"
    )
    invalidated_at = db.Column(db.DateTime, nullable=True)
    invalidated_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id"),
        nullable=True
    )
    invalidation_reason = db.Column(db.String(80), nullable=True)

    snapshot_source = db.Column(
        db.String(30),
        nullable=False,
        default="issued",
        server_default="issued"
    )
    amount_snapshot = db.Column(db.Numeric(10, 2), nullable=True)
    currency_code_snapshot = db.Column(db.String(3), nullable=False)
    payment_type_snapshot = db.Column(db.String(30), nullable=True)
    concept_snapshot = db.Column(db.String(120), nullable=True)
    period_start_snapshot = db.Column(db.Date, nullable=True)
    period_end_snapshot = db.Column(db.Date, nullable=True)
    payment_date_snapshot = db.Column(db.Date, nullable=True)
    payment_method_snapshot = db.Column(db.String(50), nullable=True)
    reference_snapshot = db.Column(db.String(120), nullable=True)
    player_name_snapshot = db.Column(db.String(200), nullable=True)
    club_name_snapshot = db.Column(db.String(120), nullable=True)
    club_location_snapshot = db.Column(db.String(120), nullable=True)
    club_state_snapshot = db.Column(db.String(120), nullable=True)
    primary_color_snapshot = db.Column(db.String(20), nullable=True)
    secondary_color_snapshot = db.Column(db.String(20), nullable=True)
    logo_url_snapshot = db.Column(db.String(500), nullable=True)

    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

    sent_at = db.Column(db.DateTime, nullable=True)
    sent_channel = db.Column(db.String(30), nullable=True)
    sent_to = db.Column(db.String(120), nullable=True)

    payment = db.relationship(
        "PlayerPayment",
        back_populates="receipts"
    )
    share_events = db.relationship(
        "PaymentReceiptShareEvent",
        back_populates="receipt",
        order_by=lambda: (
            PaymentReceiptShareEvent.created_at.desc(),
            PaymentReceiptShareEvent.id.desc()
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
            "status": self.status,
            "invalidated_at": (
                self.invalidated_at.isoformat()
                if self.invalidated_at
                else None
            ),
            "invalidated_by": self.invalidated_by,
            "invalidation_reason": self.invalidation_reason,
            "snapshot_source": self.snapshot_source,
            "amount_snapshot": (
                float(self.amount_snapshot)
                if self.amount_snapshot is not None
                else None
            ),
            "currency_code_snapshot": self.currency_code_snapshot,
            "payment_type_snapshot": self.payment_type_snapshot,
            "concept_snapshot": self.concept_snapshot,
            "period_start_snapshot": (
                self.period_start_snapshot.isoformat()
                if self.period_start_snapshot
                else None
            ),
            "period_end_snapshot": (
                self.period_end_snapshot.isoformat()
                if self.period_end_snapshot
                else None
            ),
            "payment_date_snapshot": (
                self.payment_date_snapshot.isoformat()
                if self.payment_date_snapshot
                else None
            ),
            "payment_method_snapshot": self.payment_method_snapshot,
            "reference_snapshot": self.reference_snapshot,
            "player_name_snapshot": self.player_name_snapshot,
            "club_name_snapshot": self.club_name_snapshot,
            "club_location_snapshot": self.club_location_snapshot,
            "club_state_snapshot": self.club_state_snapshot,
            "primary_color_snapshot": self.primary_color_snapshot,
            "secondary_color_snapshot": self.secondary_color_snapshot,
            "logo_url_snapshot": self.logo_url_snapshot,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "sent_channel": self.sent_channel,
            "sent_to": self.sent_to,
        }


class PaymentReceiptShareEvent(db.Model):
    """Audita el inicio de una acción de compartir, no su entrega."""

    __tablename__ = "payment_receipt_share_events"

    __table_args__ = (
        db.CheckConstraint(
            "event_type IN ('share_initiated', 'legacy_share_metadata')",
            name="ck_receipt_share_events_event_type"
        ),
        db.CheckConstraint(
            "source IN ('application', 'legacy_sent_metadata')",
            name="ck_receipt_share_events_source"
        ),
        db.Index(
            "ix_receipt_share_events_receipt_created_at",
            "receipt_id",
            "created_at"
        ),
        db.Index(
            "uq_receipt_share_events_legacy_receipt",
            "receipt_id",
            unique=True,
            postgresql_where=db.text(
                "source = 'legacy_sent_metadata'"
            ),
            sqlite_where=db.text(
                "source = 'legacy_sent_metadata'"
            )
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    receipt_id = db.Column(
        db.String(36),
        db.ForeignKey("payment_receipts.id"),
        nullable=False
    )
    club_id = db.Column(
        db.String(36),
        db.ForeignKey("clubs.id"),
        nullable=False
    )
    channel = db.Column(db.String(30), nullable=True)
    destination = db.Column(db.String(120), nullable=True)
    event_type = db.Column(
        db.String(40),
        nullable=False,
        default="share_initiated",
        server_default="share_initiated"
    )
    source = db.Column(
        db.String(40),
        nullable=False,
        default="application",
        server_default="application"
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    created_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id"),
        nullable=True
    )

    receipt = db.relationship(
        "PaymentReceipt",
        back_populates="share_events"
    )

    def serialize(self):
        return {
            "id": self.id,
            "receipt_id": self.receipt_id,
            "club_id": self.club_id,
            "channel": self.channel,
            "destination": self.destination,
            "event_type": self.event_type,
            "source": self.source,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            "created_by": self.created_by,
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

class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id"),
        nullable=False
    )

    token_hash = db.Column(db.String(255), unique=True, nullable=False)

    expires_at = db.Column(db.DateTime, nullable=False)

    used_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship(
        "User",
        backref=db.backref("password_reset_tokens", lazy=True)
    )

    def is_used(self):
        return self.used_at is not None

    def is_expired(self):
        return datetime.utcnow() > self.expires_at
