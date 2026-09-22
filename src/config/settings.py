import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# O .env é opcional. Quando não existir, os valores padrão abaixo são usados.
load_dotenv(PROJECT_ROOT / ".env")


def _get_bool(name: str, default: bool) -> bool:
    """Lê uma variável booleana aceitando valores comuns de configuração."""
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"Valor booleano inválido para {name}: {value}"
    )


def _get_int(name: str, default: int) -> int:
    """Lê uma variável de ambiente inteira."""
    value = os.getenv(name)
    return default if value is None else int(value)


def _get_float(name: str, default: float) -> float:
    """Lê uma variável de ambiente decimal."""
    value = os.getenv(name)
    return default if value is None else float(value)


def _get_project_path(name: str, default: str) -> Path:
    """Resolve caminhos relativos a partir da raiz do projeto."""
    configured = Path(os.getenv(name, default)).expanduser()

    if configured.is_absolute():
        return configured

    return PROJECT_ROOT / configured


# Ambiente e execução.
APP_ENV = os.getenv("APP_ENV", "dev").strip().lower()
BROWSER_HEADLESS = _get_bool("BROWSER_HEADLESS", False)
RESULTS_DIR = _get_project_path("RESULTS_DIR", "results")

# Fake Name Generator.
FAKE_NAME_URL = os.getenv(
    "FAKE_NAME_URL",
    "https://www.fakenamegenerator.com/gen-random-br-br.php",
)
FAKE_NAME_TIMEOUT_MS = _get_int("FAKE_NAME_TIMEOUT_MS", 15000)

# Sauce Demo.
SAUCE_DEMO_URL = os.getenv(
    "SAUCE_DEMO_URL",
    "https://www.saucedemo.com/",
)
SAUCE_USERNAME = os.getenv("SAUCE_USERNAME", "standard_user")
SAUCE_PASSWORD = os.getenv("SAUCE_PASSWORD", "secret_sauce")
SAUCE_PRODUCTS_TIMEOUT_MS = _get_int(
    "SAUCE_PRODUCTS_TIMEOUT_MS",
    15000,
)
SAUCE_PRODUCTS_RENDER_WAIT_SECONDS = _get_float(
    "SAUCE_PRODUCTS_RENDER_WAIT_SECONDS",
    1.0,
)

# Fakturama e automação visual.
FAKTURAMA_EXE = os.getenv(
    "FAKTURAMA_EXE",
    r"C:\Program Files\Fakturama2\Fakturama.exe",
)
FAKTURAMA_TERMINATION_TIMEOUT_SECONDS = _get_float(
    "FAKTURAMA_TERMINATION_TIMEOUT_SECONDS",
    10.0,
)
IMAGE_CONFIDENCE = _get_float("IMAGE_CONFIDENCE", 0.80)
IMAGE_TIMEOUT_SECONDS = _get_int("IMAGE_TIMEOUT_SECONDS", 180)
IMAGE_POLL_INTERVAL_SECONDS = _get_float(
    "IMAGE_POLL_INTERVAL_SECONDS",
    0.5,
)
FAKTURAMA_AFTER_SAVE_WAIT_SECONDS = _get_float(
    "FAKTURAMA_AFTER_SAVE_WAIT_SECONDS",
    0.5,
)
FAKTURAMA_CLOSE_WAIT_SECONDS = _get_float(
    "FAKTURAMA_CLOSE_WAIT_SECONDS",
    1.0,
)
EVIDENCE_VIEW_WAIT_SECONDS = _get_float(
    "EVIDENCE_VIEW_WAIT_SECONDS",
    1.0,
)
FIELD_CLICK_OFFSET_X = _get_int("FIELD_CLICK_OFFSET_X", 10)
FOCUS_AFTER_CLICK_WAIT_SECONDS = _get_float(
    "FOCUS_AFTER_CLICK_WAIT_SECONDS",
    0.1,
)
FOCUS_COLOR_TOLERANCE = _get_int("FOCUS_COLOR_TOLERANCE", 12)
FOCUS_MIN_MATCH_RATIO = _get_float("FOCUS_MIN_MATCH_RATIO", 0.60)
FOCUS_CLICK_MAX_ATTEMPTS = _get_int("FOCUS_CLICK_MAX_ATTEMPTS", 2)
