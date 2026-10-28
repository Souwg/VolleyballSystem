from src.api.models import (
    db,
    Attendance,
    Player,
    TeamPlayer,
    TrainingPlayer,
)


class TrainingRosterFrozenError(Exception):
    pass


def sync_training_roster(training):
    if training.status != "scheduled":
        raise TrainingRosterFrozenError()

    eligible_memberships = (
        TeamPlayer.query
        .join(Player, Player.id == TeamPlayer.player_id)
        .filter(
            TeamPlayer.team_id == training.team_id,
            Player.club_id == training.team.club_id,
            Player.is_active.is_(True)
        )
        .all()
    )

    eligible_by_player_id = {
        membership.player_id: membership
        for membership in eligible_memberships
    }

    existing_rows = TrainingPlayer.query.filter_by(
        training_id=training.id
    ).all()

    existing_by_player_id = {
        row.player_id: row
        for row in existing_rows
    }

    attendance_player_ids = {
        player_id
        for (player_id,) in db.session.query(Attendance.player_id).filter(
            Attendance.session_id == training.id
        ).all()
    }

    eligible_player_ids = set(eligible_by_player_id)
    existing_player_ids = set(existing_by_player_id)

    added_count = 0
    removed_count = 0
    updated_count = 0
    preserved_count = 0

    for player_id in eligible_player_ids - existing_player_ids:
        membership = eligible_by_player_id[player_id]

        db.session.add(TrainingPlayer(
            training_id=training.id,
            player_id=player_id,
            player_number=membership.player_number
        ))
        added_count += 1

    for player_id in eligible_player_ids & existing_player_ids:
        row = existing_by_player_id[player_id]
        membership = eligible_by_player_id[player_id]

        if row.player_number != membership.player_number:
            row.player_number = membership.player_number
            updated_count += 1

    for player_id in existing_player_ids - eligible_player_ids:
        row = existing_by_player_id[player_id]

        if player_id in attendance_player_ids:
            preserved_count += 1
            continue

        db.session.delete(row)
        removed_count += 1

    return {
        "added_count": added_count,
        "removed_count": removed_count,
        "updated_count": updated_count,
        "preserved_with_attendance_count": preserved_count,
        "total_players": (
            len(existing_rows)
            + added_count
            - removed_count
        )
    }
