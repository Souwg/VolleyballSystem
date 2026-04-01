from src.app import app
from src.api.models import db, User
from src.api.extensions import bcrypt


def seed_admin():
    with app.app_context():
        existing = User.query.filter_by(
            email="admin@system.com"
        ).first()

        if existing:
            print("✅ Admin ya existe")
            return

        admin = User(
            full_name="System Admin",
            email="admin@system.com",
            password=bcrypt.generate_password_hash(
                "12345678"
            ).decode("utf-8"),
            role="system_admin",
            first_login=False,
            is_active=True
        )

        db.session.add(admin)
        db.session.commit()

        print("🔥 Admin creado")
        print("email: admin@system.com")
        print("password: 12345678")


if __name__ == "__main__":
    seed_admin()