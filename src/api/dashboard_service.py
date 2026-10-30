from datetime import datetime, timedelta

from sqlalchemy import and_, case, exists, func, or_

from src.api.models import (
    db,
    Attendance,
    Category,
    MatchPlayer,
    MatchSession,
    PaymentReceipt,
    PaymentReceiptShareEvent,
    Player,
    PlayerPayment,
    Team,
    TeamPlayer,
    Tournament,
    TrainingPlayer,
    TrainingSession,
    User,
)
from src.api.payment_service import get_player_monthly_configuration_issue
from src.api.time_utils import get_club_today


DASHBOARD_LIST_LIMIT = 5


def get_dashboard_as_of():
    """Una única referencia temporal UTC para toda la respuesta."""
    return datetime.utcnow()


def _money(value):
    return float(value or 0)


def _player_name(first_name, last_name):
    return " ".join(part for part in [first_name, last_name] if part)


def _serialize_club_for_role(club, role):
    data = club.serialize()

    if role == "coach":
        data.pop("default_enrollment_fee", None)
        data.pop("default_monthly_fee", None)

    return data


def _get_financial_summary(club_id, today):
    month_start = today.replace(day=1)

    row = db.session.query(
        func.sum(case((PlayerPayment.status == "pending", 1), else_=0)),
        func.sum(case((PlayerPayment.status == "pending", PlayerPayment.amount), else_=0)),
        func.sum(case((PlayerPayment.status == "overdue", 1), else_=0)),
        func.sum(case((PlayerPayment.status == "overdue", PlayerPayment.amount), else_=0)),
        func.sum(case((
            (PlayerPayment.status == "paid")
            & (PlayerPayment.payment_date == today),
            1,
        ), else_=0)),
        func.sum(case((
            (PlayerPayment.status == "paid")
            & (PlayerPayment.payment_date == today),
            PlayerPayment.amount,
        ), else_=0)),
        func.sum(case((
            (PlayerPayment.status == "paid")
            & (PlayerPayment.payment_date >= month_start)
            & (PlayerPayment.payment_date <= today),
            1,
        ), else_=0)),
        func.sum(case((
            (PlayerPayment.status == "paid")
            & (PlayerPayment.payment_date >= month_start)
            & (PlayerPayment.payment_date <= today),
            PlayerPayment.amount,
        ), else_=0)),
    ).filter(PlayerPayment.club_id == club_id).one()

    pending_count = int(row[0] or 0)
    pending_amount = _money(row[1])
    overdue_count = int(row[2] or 0)
    overdue_amount = _money(row[3])

    return {
        "outstanding_count": pending_count + overdue_count,
        "outstanding_amount": pending_amount + overdue_amount,
        "pending_count": pending_count,
        "pending_amount": pending_amount,
        "overdue_count": overdue_count,
        "overdue_amount": overdue_amount,
        "paid_today_count": int(row[4] or 0),
        "paid_today_amount": _money(row[5]),
        "paid_this_month_count": int(row[6] or 0),
        "paid_this_month_amount": _money(row[7]),
    }


def _serialize_payment_row(row, include_method=False):
    payment = {
        "payment_id": row.id,
        "player_id": row.player_id,
        "player_name": _player_name(row.first_name, row.last_name),
        "amount": _money(row.amount),
        "currency_code": row.currency_code,
        "payment_date": (
            row.payment_date.isoformat()
            if row.payment_date
            else None
        ),
        "payment_type": row.payment_type,
    }

    if hasattr(row, "due_date"):
        payment["due_date"] = (
            row.due_date.isoformat()
            if row.due_date
            else None
        )

    if include_method:
        payment["payment_method"] = row.payment_method
        payment["reference"] = row.reference

    return payment


def _get_paid_without_receipt(club_id):
    issued_receipt_exists = exists().where(and_(
        PaymentReceipt.payment_id == PlayerPayment.id,
        PaymentReceipt.club_id == club_id,
        PaymentReceipt.status == "issued",
    ))

    query = db.session.query(
        PlayerPayment.id,
        PlayerPayment.player_id,
        Player.first_name,
        Player.last_name,
        PlayerPayment.amount,
        PlayerPayment.currency_code,
        PlayerPayment.payment_date,
        PlayerPayment.payment_type,
        PlayerPayment.created_at,
    ).join(
        Player,
        Player.id == PlayerPayment.player_id,
    ).filter(
        PlayerPayment.club_id == club_id,
        Player.club_id == club_id,
        PlayerPayment.status == "paid",
        ~issued_receipt_exists,
    )

    return {
        "count": query.count(),
        "payments": [
            _serialize_payment_row(row)
            for row in query.order_by(
                PlayerPayment.payment_date.desc(),
                PlayerPayment.created_at.desc(),
                PlayerPayment.id.asc(),
            ).limit(DASHBOARD_LIST_LIMIT).all()
        ],
    }


def _get_recent_payments(club_id):
    rows = db.session.query(
        PlayerPayment.id,
        PlayerPayment.player_id,
        Player.first_name,
        Player.last_name,
        PlayerPayment.amount,
        PlayerPayment.currency_code,
        PlayerPayment.payment_date,
        PlayerPayment.payment_type,
        PlayerPayment.payment_method,
        PlayerPayment.reference,
        PlayerPayment.created_at,
    ).join(
        Player,
        Player.id == PlayerPayment.player_id,
    ).filter(
        PlayerPayment.club_id == club_id,
        Player.club_id == club_id,
        PlayerPayment.status == "paid",
    ).order_by(
        PlayerPayment.payment_date.desc(),
        PlayerPayment.created_at.desc(),
        PlayerPayment.id.asc(),
    ).limit(DASHBOARD_LIST_LIMIT).all()

    return {
        "payments": [
            _serialize_payment_row(row, include_method=True)
            for row in rows
        ],
    }


def _get_upcoming_due(club_id, today):
    window_end = today + timedelta(days=7)

    row = db.session.query(
        func.sum(case((PlayerPayment.due_date == today, 1), else_=0)),
        func.sum(case((
            PlayerPayment.due_date == today,
            PlayerPayment.amount,
        ), else_=0)),
        func.sum(case((
            (PlayerPayment.due_date > today)
            & (PlayerPayment.due_date <= window_end),
            1,
        ), else_=0)),
        func.sum(case((
            (PlayerPayment.due_date > today)
            & (PlayerPayment.due_date <= window_end),
            PlayerPayment.amount,
        ), else_=0)),
    ).filter(
        PlayerPayment.club_id == club_id,
        PlayerPayment.status == "pending",
    ).one()

    rows = db.session.query(
        PlayerPayment.id,
        PlayerPayment.player_id,
        Player.first_name,
        Player.last_name,
        PlayerPayment.amount,
        PlayerPayment.currency_code,
        PlayerPayment.payment_date,
        PlayerPayment.payment_type,
        PlayerPayment.due_date,
    ).join(
        Player,
        Player.id == PlayerPayment.player_id,
    ).filter(
        PlayerPayment.club_id == club_id,
        Player.club_id == club_id,
        PlayerPayment.status == "pending",
        PlayerPayment.due_date >= today,
        PlayerPayment.due_date <= window_end,
    ).order_by(
        PlayerPayment.due_date.asc(),
        PlayerPayment.id.asc(),
    ).limit(DASHBOARD_LIST_LIMIT).all()

    return {
        "today_count": int(row[0] or 0),
        "today_amount": _money(row[1]),
        "next_7_days_count": int(row[2] or 0),
        "next_7_days_amount": _money(row[3]),
        "payments": [
            _serialize_payment_row(payment)
            for payment in rows
        ],
    }


def _get_overdue_aging(club_id, today):
    seven_days_ago = today - timedelta(days=7)
    thirty_days_ago = today - timedelta(days=30)

    row = db.session.query(
        func.sum(case((
            PlayerPayment.due_date >= seven_days_ago,
            1,
        ), else_=0)),
        func.sum(case((
            PlayerPayment.due_date >= seven_days_ago,
            PlayerPayment.amount,
        ), else_=0)),
        func.sum(case((
            (PlayerPayment.due_date < seven_days_ago)
            & (PlayerPayment.due_date >= thirty_days_ago),
            1,
        ), else_=0)),
        func.sum(case((
            (PlayerPayment.due_date < seven_days_ago)
            & (PlayerPayment.due_date >= thirty_days_ago),
            PlayerPayment.amount,
        ), else_=0)),
        func.sum(case((
            PlayerPayment.due_date < thirty_days_ago,
            1,
        ), else_=0)),
        func.sum(case((
            PlayerPayment.due_date < thirty_days_ago,
            PlayerPayment.amount,
        ), else_=0)),
    ).filter(
        PlayerPayment.club_id == club_id,
        PlayerPayment.status == "overdue",
        PlayerPayment.due_date.isnot(None),
        PlayerPayment.due_date <= today,
    ).one()

    return {
        "days_0_7": {"count": int(row[0] or 0), "amount": _money(row[1])},
        "days_8_30": {"count": int(row[2] or 0), "amount": _money(row[3])},
        "days_31_plus": {"count": int(row[4] or 0), "amount": _money(row[5])},
    }


def _get_top_outstanding_players(club_id):
    outstanding_amount = func.sum(PlayerPayment.amount)
    overdue_amount = func.sum(case((
        PlayerPayment.status == "overdue",
        PlayerPayment.amount,
    ), else_=0))

    rows = db.session.query(
        Player.id.label("player_id"),
        Player.first_name,
        Player.last_name,
        outstanding_amount.label("outstanding_amount"),
        overdue_amount.label("overdue_amount"),
        func.count(PlayerPayment.id).label("payment_count"),
    ).join(
        PlayerPayment,
        PlayerPayment.player_id == Player.id,
    ).filter(
        Player.club_id == club_id,
        PlayerPayment.club_id == club_id,
        PlayerPayment.status.in_(["pending", "overdue"]),
    ).group_by(
        Player.id,
        Player.first_name,
        Player.last_name,
    ).order_by(
        outstanding_amount.desc(),
        Player.id.asc(),
    ).limit(DASHBOARD_LIST_LIMIT).all()

    return [
        {
            "player_id": row.player_id,
            "player_name": _player_name(row.first_name, row.last_name),
            "outstanding_amount": _money(row.outstanding_amount),
            "overdue_amount": _money(row.overdue_amount),
            "payment_count": int(row.payment_count or 0),
        }
        for row in rows
    ]


def _get_payment_configuration_attention(club, today):
    effective_fee = func.coalesce(
        Player.monthly_fee,
        club.default_monthly_fee,
        0,
    )

    candidates = Player.query.filter(
        Player.club_id == club.id,
        Player.is_active.is_(True),
        or_(
            Player.enrollment_date.is_(None),
            Player.payment_control_start_date.is_(None),
            effective_fee <= 0,
        ),
    ).order_by(
        Player.created_at.asc(),
        Player.id.asc(),
    ).all()

    candidate_ids = [player.id for player in candidates]
    existing_base_payment_player_ids = set()

    if candidate_ids:
        existing_base_payment_player_ids = {
            player_id
            for (player_id,) in db.session.query(
                PlayerPayment.player_id
            ).filter(
                PlayerPayment.club_id == club.id,
                PlayerPayment.player_id.in_(candidate_ids),
                PlayerPayment.payment_type.in_(["enrollment", "monthly"]),
            ).distinct().all()
        }

    issues = []
    reason_counts = {}

    for player in candidates:
        issue = get_player_monthly_configuration_issue(
            player=player,
            club=club,
            as_of=today,
            has_existing_base_payment=(
                player.id in existing_base_payment_player_ids
            ),
        )

        if not issue:
            continue

        reason = issue["reason"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        issues.append({
            "player_id": player.id,
            "player_name": _player_name(
                player.first_name,
                player.last_name,
            ),
            "reason": reason,
            "message": issue["message"],
        })

    return {
        "requires_review_count": len(issues),
        "reason_counts": reason_counts,
        "players": issues[:DASHBOARD_LIST_LIMIT],
    }


def _serialize_training_row(row, today, include_attendance=False):
    item = {
        "id": row.id,
        "team_id": row.team_id,
        "team_name": row.team_name,
        "date": row.date.isoformat(),
        "start_time": row.start_time.isoformat() if row.start_time else None,
        "end_time": row.end_time.isoformat() if row.end_time else None,
        "location": row.location,
        "status": row.status,
        "is_today": row.date == today,
    }

    if include_attendance:
        item.update({
            "roster_count": int(row.roster_count or 0),
            "attendance_count": int(row.attendance_count or 0),
            "missing_attendance_count": (
                int(row.roster_count or 0)
                - int(row.attendance_count or 0)
            ),
        })

    return item


def _serialize_match_row(row, today):
    item = {
        "id": row.id,
        "team_id": row.team_id,
        "team_name": row.team_name,
        "date": row.date.isoformat(),
        "opponent_name": row.opponent_name,
        "location": row.location,
        "match_type": row.match_type,
        "match_step": row.match_step,
        "capture_mode": row.capture_mode,
        "result": row.result,
        "is_completed": bool(row.is_completed),
        "is_today": row.date == today,
    }

    if hasattr(row, "roster_count"):
        item["roster_count"] = int(row.roster_count or 0)

    return item


def _get_sports_sections(club_id, season_id, today):

    trainings_today_count = TrainingSession.query.join(Team).filter(
        Team.club_id == club_id,
        Team.season_id == season_id,
        TrainingSession.status == "scheduled",
        TrainingSession.date == today,
    ).count()

    upcoming_training_rows = db.session.query(
        TrainingSession.id,
        TrainingSession.team_id,
        Team.name.label("team_name"),
        TrainingSession.date,
        TrainingSession.start_time,
        TrainingSession.end_time,
        TrainingSession.location,
        TrainingSession.status,
    ).join(Team, Team.id == TrainingSession.team_id).filter(
        Team.club_id == club_id,
        Team.season_id == season_id,
        TrainingSession.status == "scheduled",
        TrainingSession.date >= today,
    ).order_by(
        TrainingSession.date.asc(),
        TrainingSession.start_time.asc(),
        TrainingSession.id.asc(),
    ).limit(DASHBOARD_LIST_LIMIT).all()

    called_roster_counts = db.session.query(
        MatchPlayer.match_id.label("match_id"),
        func.count(MatchPlayer.id).label("roster_count"),
    ).filter(
        MatchPlayer.is_called.is_(True)
    ).group_by(MatchPlayer.match_id).subquery()

    match_columns = (
        MatchSession.id,
        MatchSession.team_id,
        Team.name.label("team_name"),
        MatchSession.date,
        MatchSession.opponent_name,
        MatchSession.location,
        MatchSession.match_type,
        MatchSession.match_step,
        MatchSession.capture_mode,
        MatchSession.result,
        MatchSession.is_completed,
        func.coalesce(
            called_roster_counts.c.roster_count,
            0,
        ).label("roster_count"),
    )

    upcoming_match_rows = db.session.query(*match_columns).join(
        Team,
        Team.id == MatchSession.team_id,
    ).outerjoin(
        called_roster_counts,
        called_roster_counts.c.match_id == MatchSession.id,
    ).filter(
        Team.club_id == club_id,
        Team.season_id == season_id,
        MatchSession.is_completed.is_(False),
        MatchSession.date >= today,
    ).order_by(
        MatchSession.date.asc(),
        MatchSession.id.asc(),
    ).limit(DASHBOARD_LIST_LIMIT).all()

    open_match_filter = or_(
        MatchSession.date <= today,
        MatchSession.match_step > 0,
        MatchSession.result.isnot(None),
    )

    open_match_rows = db.session.query(*match_columns).join(
        Team,
        Team.id == MatchSession.team_id,
    ).outerjoin(
        called_roster_counts,
        called_roster_counts.c.match_id == MatchSession.id,
    ).filter(
        Team.club_id == club_id,
        Team.season_id == season_id,
        MatchSession.is_completed.is_(False),
        open_match_filter,
    ).order_by(
        MatchSession.date.asc(),
        MatchSession.id.asc(),
    ).limit(DASHBOARD_LIST_LIMIT).all()

    open_matches_count = MatchSession.query.join(Team).filter(
        Team.club_id == club_id,
        Team.season_id == season_id,
        MatchSession.is_completed.is_(False),
        open_match_filter,
    ).count()

    live_match_row = db.session.query(*match_columns).join(
        Team,
        Team.id == MatchSession.team_id,
    ).outerjoin(
        called_roster_counts,
        called_roster_counts.c.match_id == MatchSession.id,
    ).filter(
        Team.club_id == club_id,
        Team.season_id == season_id,
        MatchSession.is_completed.is_(False),
        MatchSession.capture_mode == "live",
        open_match_filter,
    ).order_by(
        MatchSession.date.asc(),
        MatchSession.id.asc(),
    ).first()

    matches_today_count = MatchSession.query.join(Team).filter(
        Team.club_id == club_id,
        Team.season_id == season_id,
        MatchSession.is_completed.is_(False),
        MatchSession.date == today,
    ).count()

    roster_counts = db.session.query(
        TrainingPlayer.training_id.label("training_id"),
        func.count(TrainingPlayer.id).label("roster_count"),
    ).group_by(TrainingPlayer.training_id).subquery()

    attendance_counts = db.session.query(
        Attendance.session_id.label("training_id"),
        func.count(Attendance.id).label("attendance_count"),
    ).group_by(Attendance.session_id).subquery()

    pending_attendance_query = db.session.query(
        TrainingSession.id,
        TrainingSession.team_id,
        Team.name.label("team_name"),
        TrainingSession.date,
        TrainingSession.start_time,
        TrainingSession.end_time,
        TrainingSession.location,
        TrainingSession.status,
        func.coalesce(roster_counts.c.roster_count, 0).label("roster_count"),
        func.coalesce(
            attendance_counts.c.attendance_count,
            0,
        ).label("attendance_count"),
    ).join(
        Team,
        Team.id == TrainingSession.team_id,
    ).outerjoin(
        roster_counts,
        roster_counts.c.training_id == TrainingSession.id,
    ).outerjoin(
        attendance_counts,
        attendance_counts.c.training_id == TrainingSession.id,
    ).filter(
        Team.club_id == club_id,
        Team.season_id == season_id,
        TrainingSession.status != "cancelled",
        TrainingSession.date <= today,
        func.coalesce(roster_counts.c.roster_count, 0) > 0,
        func.coalesce(attendance_counts.c.attendance_count, 0)
        < func.coalesce(roster_counts.c.roster_count, 0),
    )

    pending_attendance_count = pending_attendance_query.count()
    pending_attendance_rows = pending_attendance_query.order_by(
        TrainingSession.date.asc(),
        TrainingSession.start_time.asc(),
        TrainingSession.id.asc(),
    ).limit(DASHBOARD_LIST_LIMIT).all()

    return {
        "upcoming_trainings": [
            _serialize_training_row(row, today)
            for row in upcoming_training_rows
        ],
        "upcoming_matches": [
            _serialize_match_row(row, today)
            for row in upcoming_match_rows
        ],
        "open_matches": [
            _serialize_match_row(row, today)
            for row in open_match_rows
        ],
        "live_match": (
            _serialize_match_row(live_match_row, today)
            if live_match_row
            else None
        ),
        "pending_attendance": {
            "count": pending_attendance_count,
            "trainings": [
                _serialize_training_row(
                    row,
                    today,
                    include_attendance=True,
                )
                for row in pending_attendance_rows
            ],
        },
        "open_matches_count": open_matches_count,
        "today_counts": {
            "trainings_today_count": trainings_today_count,
            "matches_today_count": matches_today_count,
        },
    }


def _get_sports_structure(club_id, season_id):
    active_membership_exists = exists().where(and_(
        TeamPlayer.player_id == Player.id,
        TeamPlayer.status == "active",
        TeamPlayer.left_at.is_(None),
        TeamPlayer.team_id.in_(
            db.session.query(Team.id).filter(
                Team.club_id == club_id,
                Team.season_id == season_id,
            )
        ),
    ))

    players_query = db.session.query(
        Player.id,
        Player.first_name,
        Player.last_name,
    ).filter(
        Player.club_id == club_id,
        Player.is_active.is_(True),
        ~active_membership_exists,
    )

    active_player_membership_exists = exists().where(and_(
        TeamPlayer.team_id == Team.id,
        TeamPlayer.status == "active",
        TeamPlayer.left_at.is_(None),
        TeamPlayer.player_id == Player.id,
        Player.club_id == club_id,
        Player.is_active.is_(True),
    ))

    teams_query = db.session.query(
        Team.id,
        Team.name,
        Team.category_id,
    ).filter(
        Team.club_id == club_id,
        Team.season_id == season_id,
        ~active_player_membership_exists,
    )

    tournament_rows = db.session.query(
        Tournament.id,
        Tournament.name,
        Tournament.status,
        Tournament.start_date,
        Tournament.end_date,
    ).filter(
        Tournament.club_id == club_id,
        Tournament.season_id == season_id,
        Tournament.status == "active",
    ).order_by(
        Tournament.start_date.asc(),
        Tournament.id.asc(),
    ).limit(DASHBOARD_LIST_LIMIT).all()

    return {
        "players_without_team": {
            "count": players_query.count(),
            "players": [
                {
                    "player_id": row.id,
                    "player_name": _player_name(
                        row.first_name,
                        row.last_name,
                    ),
                }
                for row in players_query.order_by(
                    Player.last_name.asc(),
                    Player.first_name.asc(),
                    Player.id.asc(),
                ).limit(DASHBOARD_LIST_LIMIT).all()
            ],
        },
        "empty_teams": {
            "count": teams_query.count(),
            "teams": [
                {
                    "team_id": row.id,
                    "name": row.name,
                    "category_id": row.category_id,
                }
                for row in teams_query.order_by(
                    Team.name.asc(),
                    Team.id.asc(),
                ).limit(DASHBOARD_LIST_LIMIT).all()
            ],
        },
        "active_tournaments": [
            {
                "tournament_id": row.id,
                "name": row.name,
                "status": row.status,
                "start_date": row.start_date.isoformat(),
                "end_date": (
                    row.end_date.isoformat()
                    if row.end_date
                    else None
                ),
            }
            for row in tournament_rows
        ],
    }


def _get_last_official_match(club_id, today):
    row = db.session.query(
        MatchSession.id,
        MatchSession.date,
        MatchSession.opponent_name,
        MatchSession.result,
        MatchSession.home_sets,
        MatchSession.opponent_sets,
        MatchSession.capture_mode,
        MatchSession.team_id,
        Team.name.label("team_name"),
    ).join(
        Team,
        Team.id == MatchSession.team_id,
    ).filter(
        Team.club_id == club_id,
        MatchSession.is_completed.is_(True),
        MatchSession.match_type == "official",
        MatchSession.date <= today,
    ).order_by(
        MatchSession.date.desc(),
        MatchSession.id.asc(),
    ).first()

    if not row:
        return None

    return {
        "match_id": row.id,
        "team_id": row.team_id,
        "team_name": row.team_name,
        "opponent_name": row.opponent_name,
        "date": row.date.isoformat(),
        "result": row.result,
        "home_sets": row.home_sets,
        "opponent_sets": row.opponent_sets,
        "capture_mode": row.capture_mode,
    }


def _get_receipt_share_attention(club_id):
    application_receipt_ids = db.session.query(
        PaymentReceiptShareEvent.receipt_id
    ).filter(
        PaymentReceiptShareEvent.club_id == club_id,
        PaymentReceiptShareEvent.source == "application",
    )

    query = db.session.query(
        PaymentReceipt.id,
        PaymentReceipt.payment_id,
        PaymentReceipt.receipt_number,
        PaymentReceipt.player_name_snapshot,
        PaymentReceipt.generated_at,
    ).filter(
        PaymentReceipt.club_id == club_id,
        PaymentReceipt.status == "issued",
        PaymentReceipt.id.notin_(application_receipt_ids),
    )

    count = query.count()
    rows = query.order_by(
        PaymentReceipt.generated_at.asc(),
        PaymentReceipt.id.asc(),
    ).limit(DASHBOARD_LIST_LIMIT).all()

    return {
        "issued_without_application_share_count": count,
        "receipts": [
            {
                "receipt_id": row.id,
                "payment_id": row.payment_id,
                "receipt_number": row.receipt_number,
                "player_name": row.player_name_snapshot,
                "generated_at": (
                    row.generated_at.isoformat()
                    if row.generated_at
                    else None
                ),
            }
            for row in rows
        ],
    }


def _get_missing_payment_contacts(club_id):
    outstanding_player_ids = db.session.query(
        PlayerPayment.player_id
    ).filter(
        PlayerPayment.club_id == club_id,
        PlayerPayment.status.in_(["pending", "overdue"]),
    ).distinct()

    query = db.session.query(
        Player.id,
        Player.first_name,
        Player.last_name,
    ).filter(
        Player.club_id == club_id,
        Player.is_active.is_(True),
        Player.id.in_(outstanding_player_ids),
        or_(
            Player.representative_phone.is_(None),
            func.trim(Player.representative_phone) == "",
        ),
    )

    count = query.count()
    rows = query.order_by(
        Player.last_name.asc(),
        Player.first_name.asc(),
        Player.id.asc(),
    ).limit(DASHBOARD_LIST_LIMIT).all()

    return {
        "outstanding_players_without_contact_count": count,
        "players": [
            {
                "player_id": row.id,
                "player_name": _player_name(row.first_name, row.last_name),
            }
            for row in rows
        ],
    }


def _get_inactive_people_attention(club_id):
    player_query = db.session.query(
        Player.id,
        Player.first_name,
        Player.last_name,
    ).filter(
        Player.club_id == club_id,
        Player.is_active.is_(False),
    )
    user_query = db.session.query(
        User.id,
        User.full_name,
        User.role,
    ).filter(
        User.club_id == club_id,
        User.role.in_(["coach", "staff"]),
        User.is_active.is_(False),
    )

    return {
        "inactive_players_count": player_query.count(),
        "inactive_players": [
            {
                "player_id": row.id,
                "player_name": _player_name(row.first_name, row.last_name),
            }
            for row in player_query.order_by(
                Player.last_name.asc(),
                Player.first_name.asc(),
                Player.id.asc(),
            ).limit(DASHBOARD_LIST_LIMIT).all()
        ],
        "inactive_users_count": user_query.count(),
        "inactive_users": [
            {
                "user_id": row.id,
                "full_name": row.full_name,
                "role": row.role,
            }
            for row in user_query.order_by(
                User.full_name.asc(),
                User.id.asc(),
            ).limit(DASHBOARD_LIST_LIMIT).all()
        ],
    }


def _weekly_counts(model, club_id, week_start, season_id=None):
    expressions = []

    for weeks_ago in range(3, -1, -1):
        period_start = week_start - timedelta(weeks=weeks_ago)
        period_end = period_start + timedelta(days=7)
        expressions.append(func.sum(case((
            (model.created_at >= period_start)
            & (model.created_at < period_end),
            1,
        ), else_=0)))

    query = db.session.query(*expressions).filter(
        model.club_id == club_id
    )

    if model is Team and season_id is not None:
        query = query.filter(Team.season_id == season_id)

    row = query.one()
    return [int(value or 0) for value in row]


def _get_legacy_contract(club, season_id, as_of, role, today):
    week_start = (
        as_of - timedelta(days=as_of.weekday())
    ).replace(hour=0, minute=0, second=0, microsecond=0)

    total_categories = Category.query.filter_by(club_id=club.id).count()
    total_teams = Team.query.filter_by(
        club_id=club.id,
        season_id=season_id,
    ).count()
    player_counts = db.session.query(
        func.count(Player.id),
        func.sum(case((Player.is_active.is_(True), 1), else_=0)),
        func.sum(case((Player.is_active.is_(False), 1), else_=0)),
    ).filter(Player.club_id == club.id).one()
    total_players = int(player_counts[0] or 0)
    active_players = int(player_counts[1] or 0)
    inactive_players = int(player_counts[2] or 0)
    total_trainings = TrainingSession.query.join(Team).filter(
        Team.club_id == club.id
    ).count()
    teams_this_week = Team.query.filter(
        Team.club_id == club.id,
        Team.season_id == season_id,
        Team.created_at >= week_start,
        Team.created_at <= as_of,
    ).count()
    players_this_week = Player.query.filter(
        Player.club_id == club.id,
        Player.created_at >= week_start,
        Player.created_at <= as_of,
    ).count()

    next_match_row = db.session.query(
        MatchSession,
        Team.name.label("team_name"),
    ).join(Team, Team.id == MatchSession.team_id).filter(
        Team.club_id == club.id,
        Team.season_id == season_id,
        MatchSession.is_completed.is_(False),
        MatchSession.date >= today,
    ).order_by(
        MatchSession.date.asc(),
        MatchSession.id.asc(),
    ).first()

    if not next_match_row:
        next_match_row = db.session.query(
            MatchSession,
            Team.name.label("team_name"),
        ).join(Team, Team.id == MatchSession.team_id).filter(
            Team.club_id == club.id,
            Team.season_id == season_id,
            MatchSession.is_completed.is_(False),
            MatchSession.date < today,
        ).order_by(
            MatchSession.date.desc(),
            MatchSession.id.asc(),
        ).first()

    next_match = None

    if next_match_row:
        match, team_name = next_match_row
        serialized_match = match.serialize()

        if role == "coach":
            serialized_match.pop("referee_fee", None)
            serialized_match.pop("tournament_team", None)

        next_match = {
            **serialized_match,
            "team_name": team_name,
        }

    return {
        "stats": {
            "total_categories": total_categories,
            "total_teams": total_teams,
            "total_players": total_players,
            "active_players": active_players,
            "inactive_players": inactive_players,
            "total_trainings": total_trainings,
            "teams_this_week": teams_this_week,
            "players_this_week": players_this_week,
            "active_players_percentage": (
                round((active_players / total_players) * 100)
                if total_players > 0
                else 0
            ),
            "teams_weekly_trend": _weekly_counts(
                Team,
                club.id,
                week_start,
                season_id=season_id,
            ),
            "players_weekly_trend": _weekly_counts(
                Player,
                club.id,
                week_start,
            ),
        },
        "next_match": next_match,
    }


def build_club_dashboard(user, club, as_of=None, active_season_id=None):
    as_of = as_of or get_dashboard_as_of()
    today = get_club_today(club, utc_now=as_of)
    response = {
        "role": user.role,
        "as_of": as_of.replace(microsecond=0).isoformat() + "Z",
        "club": _serialize_club_for_role(club, user.role),
        "sections": {},
    }

    financial_summary = None
    payment_configuration = None
    sports = None
    sports_structure = None
    paid_without_receipt = None
    recent_payments = None
    upcoming_due = None
    overdue_aging = None
    top_outstanding_players = None
    receipt_share_attention = None
    missing_payment_contacts = None
    sports_today = None

    if user.role in ["club_owner", "staff"]:
        financial_summary = _get_financial_summary(club.id, today)
        payment_configuration = _get_payment_configuration_attention(
            club,
            today,
        )
        paid_without_receipt = _get_paid_without_receipt(club.id)
        recent_payments = _get_recent_payments(club.id)
        upcoming_due = _get_upcoming_due(club.id, today)
        overdue_aging = _get_overdue_aging(club.id, today)
        top_outstanding_players = _get_top_outstanding_players(club.id)
        receipt_share_attention = _get_receipt_share_attention(club.id)

    if user.role in ["club_owner", "coach"]:
        sports = _get_sports_sections(
            club.id,
            active_season_id,
            today,
        )
        sports_today = sports.pop("today_counts")
        sports_structure = _get_sports_structure(
            club.id,
            active_season_id,
        )

    if user.role == "club_owner":
        response["sections"] = {
            "today": {
                **sports_today,
                "paid_today_count": financial_summary["paid_today_count"],
                "paid_today_amount": financial_summary["paid_today_amount"],
                "overdue_count": financial_summary["overdue_count"],
            },
            "finance": financial_summary,
            "payment_configuration": payment_configuration,
            "operations": sports,
            "paid_without_receipt": paid_without_receipt,
            "recent_payments": recent_payments,
            "upcoming_due": upcoming_due,
            "overdue_aging": overdue_aging,
            "top_outstanding_players": top_outstanding_players,
            "receipt_share_attention": receipt_share_attention,
            **sports_structure,
            "inactive_people": _get_inactive_people_attention(club.id),
            "attention_summary": {
                "overdue_payments": financial_summary["overdue_count"],
                "paid_without_receipt": paid_without_receipt["count"],
                "issued_without_application_share": (
                    receipt_share_attention[
                        "issued_without_application_share_count"
                    ]
                ),
                "payment_configuration_review": (
                    payment_configuration["requires_review_count"]
                ),
                "pending_attendance": sports[
                    "pending_attendance"
                ]["count"],
                "open_matches": sports["open_matches_count"],
            },
        }
    elif user.role == "coach":
        response["sections"] = {
            "today": {
                **sports_today,
                "pending_attendance_count": sports[
                    "pending_attendance"
                ]["count"],
                "open_matches_count": sports["open_matches_count"],
            },
            "agenda": sports,
            **sports_structure,
            "last_official_match": _get_last_official_match(
                club.id,
                today,
            ),
        }
    elif user.role == "staff":
        missing_payment_contacts = _get_missing_payment_contacts(club.id)
        response["sections"] = {
            "today": {
                "paid_today_count": financial_summary["paid_today_count"],
                "paid_today_amount": financial_summary["paid_today_amount"],
                "overdue_count": financial_summary["overdue_count"],
                "due_today_count": upcoming_due["today_count"],
                "due_today_amount": upcoming_due["today_amount"],
            },
            "finance": financial_summary,
            "payment_configuration": payment_configuration,
            "paid_without_receipt": paid_without_receipt,
            "recent_payments": recent_payments,
            "upcoming_due": upcoming_due,
            "overdue_aging": overdue_aging,
            "top_outstanding_players": top_outstanding_players,
            "receipt_share_attention": receipt_share_attention,
            "missing_payment_contacts": missing_payment_contacts,
            "attention_summary": {
                "overdue_payments": financial_summary["overdue_count"],
                "paid_without_receipt": paid_without_receipt["count"],
                "issued_without_application_share": (
                    receipt_share_attention[
                        "issued_without_application_share_count"
                    ]
                ),
                "payment_configuration_review": (
                    payment_configuration["requires_review_count"]
                ),
                "missing_payment_contacts": (
                    missing_payment_contacts[
                        "outstanding_players_without_contact_count"
                    ]
                ),
            },
        }

    if user.role in ["club_owner", "coach"]:
        response.update(
            _get_legacy_contract(
                club,
                active_season_id,
                as_of,
                user.role,
                today,
            )
        )

    return response
