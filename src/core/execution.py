import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


LOGGER_NAME = "rpa"
EXECUTION_TIMESTAMP_FORMAT = "%Y-%m-%d_%H%M%S"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(message)s"


@dataclass(frozen=True)
class ExecutionPaths:
    """Caminhos gerados para uma única execução do RPA."""

    run_dir: Path
    screenshots_dir: Path
    buyer_csv: Path
    products_csv: Path
    log_file: Path
    customer_screenshot: Path
    products_screenshot: Path
    error_screenshot: Path


def create_execution_paths(results_dir) -> ExecutionPaths:
    """Cria uma pasta exclusiva para a execução atual."""
    base_dir = Path(results_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime(EXECUTION_TIMESTAMP_FORMAT)
    run_dir = _unique_run_directory(base_dir, timestamp)
    screenshots_dir = run_dir / "screenshots"

    screenshots_dir.mkdir(parents=True)

    return ExecutionPaths(
        run_dir=run_dir,
        screenshots_dir=screenshots_dir,
        buyer_csv=run_dir / "buyer.csv",
        products_csv=run_dir / "products.csv",
        log_file=run_dir / "execution.log",
        customer_screenshot=screenshots_dir / "customer_registered.png",
        products_screenshot=screenshots_dir / "products_registered.png",
        error_screenshot=screenshots_dir / "error.png",
    )


def configure_execution_logger(log_file) -> logging.Logger:
    """Configura log em arquivo e console para a execução atual."""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    formatter = logging.Formatter(
        LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )

    file_handler = logging.FileHandler(
        log_path,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def _unique_run_directory(base_dir: Path, timestamp: str) -> Path:
    """Evita colisão caso duas execuções iniciem no mesmo segundo."""
    candidate = base_dir / timestamp
    suffix = 1

    while candidate.exists():
        candidate = base_dir / f"{timestamp}_{suffix:02d}"
        suffix += 1

    return candidate
