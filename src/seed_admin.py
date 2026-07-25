import os

from src.app import app
from src.api.models import db, User
from src.api.extensions import bcrypt


def seed_admin():
    admin_email = os.getenv(
        "ADMIN_EMAIL",
        "admin@sportflow.club"
    ).strip().lower()

    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_password:
        raise RuntimeError(
            "La variable ADMIN_PASSWORD no está configurada."
        )

    with app.app_context():
        existing = User.query.filter_by(
            email=admin_email
        ).first()

        if existing:
            print("✅ Admin ya existe")
            return

        admin = User(
            full_name="System Admin",
            email=admin_email,
            password=bcrypt.generate_password_hash(
                admin_password
            ).decode("utf-8"),
            role="system_admin",
            first_login=False,
            is_active=True
        )

        db.session.add(admin)
        db.session.commit()

        print("🔥 Admin creado")
        print(f"email: {admin_email}")


if __name__ == "__main__":
    seed_admin()
