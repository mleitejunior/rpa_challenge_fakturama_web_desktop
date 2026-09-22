import logging
import sys
import types
from pathlib import Path

import pytest

# Este cenário valida a orquestração sem depender de uma sessão gráfica real.
# O módulo desktop é importado pelo main, então fornecemos um stub de pyautogui
# antes do import para permitir a execução também em ambientes headless/CI.
fake_pyautogui = types.ModuleType("pyautogui")
fake_pyautogui.ImageNotFoundException = Exception
sys.modules["pyautogui"] = fake_pyautogui

import main as app
from src.repositories.csv_repository import load_buyer, load_products


pytestmark = pytest.mark.validation


class FakeBrowser:
    def __init__(self):
        self.closed = False

    def new_page(self):
        return object()

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser

    def launch(self, headless=False):
        return self.browser


class FakePlaywright:
    def __init__(self, browser):
        self.chromium = FakeChromium(browser)


class FakePlaywrightManager:
    def __init__(self, browser):
        self.playwright = FakePlaywright(browser)

    def __enter__(self):
        return self.playwright

    def __exit__(self, exc_type, exc, tb):
        return False


def _latest_run_dir(results_dir: Path) -> Path:
    run_dirs = [path for path in results_dir.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    return run_dirs[0]


def _close_execution_logger():
    logger = logging.getLogger("rpa")

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def _create_screenshot(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-png-evidence")
    return path


def _prepare_main(monkeypatch, tmp_path, buyer_data, products_data):
    browser = FakeBrowser()
    calls = {
        "customer": [],
        "products": [],
        "terminate": 0,
        "open": 0,
        "close": 0,
    }

    monkeypatch.setattr(app, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(
        app,
        "sync_playwright",
        lambda: FakePlaywrightManager(browser),
    )
    monkeypatch.setattr(app, "scrape_buyer", lambda page: buyer_data)
    monkeypatch.setattr(app, "scrape_products", lambda page: products_data)

    def fake_terminate_existing_fakturama():
        calls["terminate"] += 1
        return False

    def fake_open_fakturama():
        calls["open"] += 1

    def fake_close_fakturama():
        calls["close"] += 1

    def fake_register_customer(buyer):
        calls["customer"].append(buyer.copy())

    def fake_register_product(product):
        calls["products"].append(product.copy())

    monkeypatch.setattr(
        app,
        "terminate_existing_fakturama",
        fake_terminate_existing_fakturama,
    )
    monkeypatch.setattr(app, "open_fakturama", fake_open_fakturama)
    monkeypatch.setattr(app, "close_fakturama", fake_close_fakturama)
    monkeypatch.setattr(app, "register_customer", fake_register_customer)
    monkeypatch.setattr(app, "register_product", fake_register_product)
    monkeypatch.setattr(
        app,
        "capture_customer_evidence",
        lambda path: _create_screenshot(path),
    )
    monkeypatch.setattr(
        app,
        "capture_products_evidence",
        lambda path: _create_screenshot(path),
    )
    monkeypatch.setattr(
        app,
        "capture_screenshot",
        lambda path: _create_screenshot(path),
    )

    return browser, calls


def test_main_success_creates_mandatory_outputs_and_registers_all_items(
    monkeypatch,
    tmp_path,
    buyer_data,
    products_data,
):
    browser, calls = _prepare_main(
        monkeypatch,
        tmp_path,
        buyer_data,
        products_data,
    )

    csv_buyer = {**buyer_data, "first_name": "Comprador do CSV"}
    csv_products = [
        {**product, "name": f'{product["name"]} - CSV'}
        for product in products_data
    ]

    monkeypatch.setattr(app, "load_buyer", lambda path: csv_buyer)
    monkeypatch.setattr(app, "load_products", lambda path: csv_products)

    try:
        app.main()
    finally:
        _close_execution_logger()

    run_dir = _latest_run_dir(tmp_path)

    assert browser.closed is True
    assert calls["terminate"] == 1
    assert calls["open"] == 1
    assert calls["close"] == 1
    assert calls["customer"] == [csv_buyer]
    assert calls["products"] == csv_products

    assert load_buyer(run_dir / "buyer.csv") == buyer_data
    assert load_products(run_dir / "products.csv") == products_data

    customer_evidence = run_dir / "screenshots" / "customer_registered.png"
    products_evidence = run_dir / "screenshots" / "products_registered.png"
    log_file = run_dir / "execution.log"

    assert customer_evidence.exists()
    assert products_evidence.exists()
    assert log_file.exists()

    log_content = log_file.read_text(encoding="utf-8")

    assert "Compradores cadastrados: 1/1" in log_content
    assert f"Produtos cadastrados: {len(products_data)}/{len(products_data)}" in log_content
    assert "Execução finalizada com sucesso" in log_content


def test_main_failure_captures_error_evidence_and_closes_fakturama(
    monkeypatch,
    tmp_path,
    buyer_data,
    products_data,
):
    browser, calls = _prepare_main(
        monkeypatch,
        tmp_path,
        buyer_data,
        products_data,
    )

    def fail_on_second_product(product):
        calls["products"].append(product.copy())

        if product["item_number"] == products_data[1]["item_number"]:
            raise RuntimeError("falha simulada no cadastro do produto")

    monkeypatch.setattr(app, "register_product", fail_on_second_product)

    try:
        with pytest.raises(
            RuntimeError,
            match="falha simulada no cadastro do produto",
        ):
            app.main()
    finally:
        _close_execution_logger()

    run_dir = _latest_run_dir(tmp_path)
    log_file = run_dir / "execution.log"
    error_evidence = run_dir / "screenshots" / "error.png"

    assert browser.closed is True
    assert calls["terminate"] == 1
    assert calls["open"] == 1
    assert calls["close"] == 1
    assert calls["customer"] == [buyer_data]
    assert len(calls["products"]) == 2
    assert error_evidence.exists()

    log_content = log_file.read_text(encoding="utf-8")

    assert "Execução interrompida por erro" in log_content
    assert "Produtos cadastrados: 1/2" in log_content
    assert "Execução finalizada com falha" in log_content

def test_main_close_failure_marks_execution_as_failed(
    monkeypatch,
    tmp_path,
    buyer_data,
    products_data,
):
    browser, calls = _prepare_main(
        monkeypatch,
        tmp_path,
        buyer_data,
        products_data,
    )

    def fail_to_close_fakturama():
        calls["close"] += 1
        raise RuntimeError("falha simulada ao fechar Fakturama")

    monkeypatch.setattr(app, "close_fakturama", fail_to_close_fakturama)

    try:
        with pytest.raises(
            RuntimeError,
            match="falha simulada ao fechar Fakturama",
        ):
            app.main()
    finally:
        _close_execution_logger()

    run_dir = _latest_run_dir(tmp_path)
    log_file = run_dir / "execution.log"

    assert browser.closed is True
    assert calls["terminate"] == 1
    assert calls["open"] == 1
    assert calls["close"] == 1

    log_content = log_file.read_text(encoding="utf-8")

    assert "Falha ao fechar o Fakturama" in log_content
    assert "Execução finalizada com falha" in log_content
    assert "Execução finalizada com sucesso" not in log_content

