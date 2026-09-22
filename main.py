from pathlib import Path

from playwright.sync_api import sync_playwright

from src.core.execution import (
    configure_execution_logger,
    create_execution_paths,
)
from src.desktop.fakturama import (
    capture_customer_evidence,
    capture_products_evidence,
    capture_screenshot,
    close_fakturama,
    open_fakturama,
    register_customer,
    register_product,
)
from src.repositories.csv_repository import (
    load_buyer,
    load_products,
    save_buyer,
    save_products,
)
from src.web.buyer_scraper import scrape_buyer
from src.web.sauce_demo import scrape_products


BROWSER_HEADLESS = False

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"


def main():
    execution = create_execution_paths(RESULTS_DIR)
    logger = configure_execution_logger(execution.log_file)

    buyer = None
    products = []
    customer_registered = 0
    products_registered = 0
    fakturama_opened = False
    success = False

    logger.info("Execução iniciada")
    logger.info("Pasta de resultados: %s", execution.run_dir)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=BROWSER_HEADLESS,
            )
            page = browser.new_page()

            try:
                logger.info("Coleta do comprador iniciada")
                buyer = scrape_buyer(page)
                logger.info(
                    "Comprador coletado: %s %s",
                    buyer["first_name"],
                    buyer["last_name"],
                )

                logger.info("Login e coleta do catálogo SauceDemo iniciados")
                products = scrape_products(page)
                logger.info("Produtos encontrados: %d", len(products))

                for index, product in enumerate(products, start=1):
                    logger.info(
                        "Produto [%d/%d] coletado: %s | %s",
                        index,
                        len(products),
                        product["item_number"],
                        product["name"],
                    )
            finally:
                browser.close()

        save_buyer(buyer, execution.buyer_csv)
        logger.info("Comprador persistido em: %s", execution.buyer_csv)

        save_products(products, execution.products_csv)
        logger.info(
            "Catálogo de produtos persistido em: %s",
            execution.products_csv,
        )

        # Os CSVs são a ponte de dados entre a etapa web e a etapa desktop.
        buyer = load_buyer(execution.buyer_csv)
        products = load_products(execution.products_csv)
        logger.info("Dados recarregados dos CSVs para a etapa desktop")

        logger.info("Abertura do Fakturama iniciada")
        open_fakturama()
        fakturama_opened = True
        logger.info("Fakturama disponível")

        logger.info("Cadastro do comprador no Fakturama iniciado")

        try:
            register_customer(buyer)
        except Exception:
            logger.exception(
                "Falha ao cadastrar comprador: %s %s",
                buyer["first_name"],
                buyer["last_name"],
            )
            raise

        customer_registered = 1
        logger.info("Comprador cadastrado com sucesso")

        customer_evidence = capture_customer_evidence(
            execution.customer_screenshot
        )
        logger.info(
            "Evidência do comprador salva em: %s",
            customer_evidence,
        )

        total_products = len(products)

        for index, product in enumerate(products, start=1):
            logger.info(
                "Cadastro do produto [%d/%d] iniciado: %s | %s",
                index,
                total_products,
                product["item_number"],
                product["name"],
            )

            try:
                register_product(product)
            except Exception:
                logger.exception(
                    "Falha ao cadastrar produto [%d/%d]: %s | %s",
                    index,
                    total_products,
                    product["item_number"],
                    product["name"],
                )
                raise

            products_registered += 1

            logger.info(
                "Produto [%d/%d] cadastrado com sucesso: %s | %s",
                index,
                total_products,
                product["item_number"],
                product["name"],
            )

        products_evidence = capture_products_evidence(
            execution.products_screenshot
        )
        logger.info(
            "Evidência dos produtos salva em: %s",
            products_evidence,
        )

        success = True

    except Exception:
        logger.exception("Execução interrompida por erro")

        if fakturama_opened:
            try:
                error_screenshot = capture_screenshot(
                    execution.error_screenshot
                )
                logger.error(
                    "Screenshot de erro salvo em: %s",
                    error_screenshot,
                )
            except Exception:
                logger.exception(
                    "Não foi possível capturar screenshot da falha"
                )

        raise

    finally:
        if fakturama_opened:
            try:
                close_fakturama()
                logger.info("Fakturama fechado")
            except Exception:
                logger.exception("Falha ao fechar o Fakturama")

        logger.info(
            "Compradores cadastrados: %d/1",
            customer_registered,
        )
        logger.info(
            "Produtos cadastrados: %d/%d",
            products_registered,
            len(products),
        )

        if success:
            logger.info("Execução finalizada com sucesso")
        else:
            logger.error("Execução finalizada com falha")


if __name__ == "__main__":
    main()
