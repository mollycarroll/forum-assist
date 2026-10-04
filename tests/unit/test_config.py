import shutil
from pathlib import Path

import pytest

from forum_assist.config import Settings

EXAMPLE_YAML = Path(__file__).parents[2] / "config.example.yaml"


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    shutil.copy(EXAMPLE_YAML, tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_defaults_load_from_yaml(isolated_cwd: Path) -> None:
    settings = Settings()
    assert settings.db_url == "sqlite:///data/forum_assist.db"
    assert settings.log_level == "INFO"


def test_env_var_overrides_yaml(isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORUM_ASSIST_DB_URL", "sqlite:///data/overridden.db")
    settings = Settings()
    assert settings.db_url == "sqlite:///data/overridden.db"
