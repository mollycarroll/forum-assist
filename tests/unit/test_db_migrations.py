from pathlib import Path

from alembic import command
from alembic.config import Config

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


def test_migrations_apply_and_revert(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
