"""Run migrations without ever printing connection strings or driver error details."""
from alembic import command
from alembic.config import Config

if __name__ == "__main__":
    try:
        command.upgrade(Config("alembic.ini"), "head")
    except Exception as exc:
        print(f"Migration failed ({type(exc).__name__}); verify database connectivity and permissions.")
        raise SystemExit(1) from None
    print("MySQL migrations applied.")
