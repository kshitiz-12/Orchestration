"""Reset prototype DB and reload seed + demo emails."""

from pathlib import Path

from sqlmodel import SQLModel

from app.core.config import get_settings
from app.core.database import get_engine, init_db
from scripts.load_demo_emails import main as load_demo
from scripts.seed import seed
from sqlmodel import Session


def main():
    settings = get_settings()
    if settings.is_sqlite and settings.database_url.startswith("sqlite:///./"):
        db_path = Path("orchestration.db")
        if db_path.exists():
            db_path.unlink()
            print("Removed orchestration.db")
    else:
        engine = get_engine()
        SQLModel.metadata.drop_all(engine)
        print("Dropped all tables")

    # Recreate engine cache cleared by deleting sqlite file; force re-init
    import app.core.database as dbmod

    dbmod._engine = None
    init_db()
    with Session(get_engine()) as session:
        tid = seed(session)
        print(f"Reseeded tenant={tid}")
    load_demo(process=True)


if __name__ == "__main__":
    main()
