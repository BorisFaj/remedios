import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

import importlib


def test_oracle_connectivity():
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
