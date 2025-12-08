import logging


def setup_logging():
    """Глобальная настройка логирования (UTF-8 с BOM для Windows)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("pc_guardian_agent.log", encoding="utf-8-sig"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger(__name__)

