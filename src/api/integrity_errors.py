def violates_named_constraint(error, constraint_names):
    """Return True only for one of the expected database constraints."""
    constraint_name = getattr(
        getattr(error.orig, "diag", None),
        "constraint_name",
        None,
    )

    if constraint_name:
        return constraint_name in constraint_names

    # SQLite does not expose PostgreSQL's ``diag.constraint_name``. Keeping
    # this fallback also makes local tests exercise the same translation path.
    message = str(error.orig).lower()
    return any(name.lower() in message for name in constraint_names)
