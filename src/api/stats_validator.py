def validate_match_stats(data):
    def to_int(value):
        try:
            return max(0, int(value))
        except:
            return 0


    stats = {
        "attacks_total": to_int(data.get("attacks_total")),
        "attacks_positive": to_int(data.get("attacks_positive")),
        "attacks_neutral": to_int(data.get("attacks_neutral")),
        "attacks_errors": to_int(data.get("attacks_errors")),

        "receptions_total": to_int(data.get("receptions_total")),
        "receptions_positive": to_int(data.get("receptions_positive")),
        "receptions_neutral": to_int(data.get("receptions_neutral")),
        "receptions_negative": to_int(data.get("receptions_negative")),

        "defenses_total": to_int(data.get("defenses_total")),
        "defenses_positive": to_int(data.get("defenses_positive")),
        "defenses_neutral": to_int(data.get("defenses_neutral")),
        "defenses_negative": to_int(data.get("defenses_negative")),

        "sets_total": to_int(data.get("sets_total")),
        "sets_positive": to_int(data.get("sets_positive")),
        "sets_neutral": to_int(data.get("sets_neutral")),
        "sets_errors": to_int(data.get("sets_errors")),

        "serves_total": to_int(data.get("serves_total")),
        "serves_in": to_int(data.get("serves_in")),
        "serves_aces": to_int(data.get("serves_aces")),
        "serves_errors": to_int(data.get("serves_errors")),

        "blocks_total": to_int(data.get("blocks_total")),
        "blocks_points": to_int(data.get("blocks_points")),
        "blocks_neutral": to_int(data.get("blocks_neutral")),
        "blocks_errors": to_int(data.get("blocks_errors")),
    }

    def validate_group(total, values, error_code):
        if sum(values) != total:
            return False, error_code
        return True, None

    checks = [
        validate_group(
            stats["attacks_total"],
            [
                stats["attacks_positive"],
                stats["attacks_neutral"],
                stats["attacks_errors"]
            ],
            "INVALID_ATTACK_STATS"
        ),
        validate_group(
            stats["receptions_total"],
            [
                stats["receptions_positive"],
                stats["receptions_neutral"],
                stats["receptions_negative"]
            ],
            "INVALID_RECEPTION_STATS"
        ),
        validate_group(
            stats["defenses_total"],
            [
                stats["defenses_positive"],
                stats["defenses_neutral"],
                stats["defenses_negative"]
            ],
            "INVALID_DEFENSE_STATS"
        ),
        validate_group(
            stats["sets_total"],
            [
                stats["sets_positive"],
                stats["sets_neutral"],
                stats["sets_errors"]
            ],
            "INVALID_SET_STATS"
        ),
        validate_group(
            stats["serves_total"],
            [
                stats["serves_in"],
                stats["serves_aces"],
                stats["serves_errors"]
            ],
            "INVALID_SERVE_STATS"
        ),
        validate_group(
            stats["blocks_total"],
            [
                stats["blocks_points"],
                stats["blocks_neutral"],
                stats["blocks_errors"]
            ],
            "INVALID_BLOCK_STATS"
        ),
    ]

    for valid, error in checks:
        if not valid:
            return None, error

    return stats, None