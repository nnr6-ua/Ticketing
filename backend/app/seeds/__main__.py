from app.core.config import settings
from app.db.session import SessionLocal
from app.seeds.seed import seed


def main() -> None:
    settings.attachments_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        seed(db)
    print("Catálogos iniciales y empleado demo creados.")


if __name__ == "__main__":
    main()
