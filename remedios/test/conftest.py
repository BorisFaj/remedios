import os
import pytest
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Carga automáticamente las variables de .env para todos los tests."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
