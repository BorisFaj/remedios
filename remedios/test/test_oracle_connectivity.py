import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

import importlib


def _load_test_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


@pytest.fixture(scope="module", autouse=True)
def load_env():
    _load_test_env()


def test_oracle_connectivity(load_env):
    required = ["ORACLE_DSN", "ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_WALLET_PATH"]
    missing = [k for k in required if not os.getenv(k)]
    assert not missing, f"Faltan variables ORACLE_*: {', '.join(missing)} (define en entorno o en test/.env)"

    # Recargar sender tras cargar el entorno para que coja las variables
    from remedios.log import sender
    importlib.reload(sender)

    engine = sender.get_engine()
    assert engine is not None, "Engine no inicializado; revisa variables ORACLE_*"

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 FROM dual"))
            assert result.scalar() == 1
    except OperationalError as exc:
        pytest.fail(f"Conexión a Oracle falló: {exc}")
