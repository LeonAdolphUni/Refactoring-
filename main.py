# ============================================================
# WICHTIG: Umgebungsvariablen MÜSSEN vor allen Imports stehen!
# HuggingFace Symlink-Fix für Firmen-Laptops mit Firewall
# ============================================================
import os

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "0"

import logging

from src.config import Config
from src.toolset import PDFReader
from src.agent import RAGAgent
from tester import run_tests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Haupteinstiegspunkt für das RAG-System."""
    logger.info("🚀 Starte RAG-System...")

    config = Config()
    logger.info(
        "✅ Konfiguration geladen (Deployment: %s)",
        config.azure_openai_deployment,
    )

    reader = PDFReader()
    logger.info("✅ PDFReader initialisiert")

    agent = RAGAgent(config=config, reader=reader)
    logger.info("✅ RAG-Agent initialisiert")

    run_tests(agent)

    logger.info("🏁 RAG-System beendet.")


if __name__ == "__main__":
    main()
