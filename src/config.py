"""Zentrale Konfiguration für das RAG-System.

Lädt Umgebungsvariablen aus der .env-Datei und stellt
eine typisierte Konfigurationsklasse bereit.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Zentrale Konfigurationsklasse für das RAG-System.

    Liest alle erforderlichen Einstellungen aus Umgebungsvariablen,
    die optional über eine .env-Datei bereitgestellt werden können.
    """

    def __init__(self) -> None:
        """Initialisiert die Konfiguration aus Umgebungsvariablen."""
        self.azure_openai_endpoint: str = os.environ.get(
            "AZURE_OPENAI_ENDPOINT", ""
        )
        self.azure_openai_api_key: str = os.environ.get(
            "AZURE_OPENAI_API_KEY", ""
        )
        self.azure_openai_api_version: str = os.environ.get(
            "AZURE_OPENAI_API_VERSION", "2024-10-21"
        )
        self.azure_openai_deployment: str = os.environ.get(
            "AZURE_OPENAI_DEPLOYMENT", "gpt-4o"
        )
        self.llm_timeout: int = int(os.environ.get("LLM_TIMEOUT", "30"))
        self.max_iterations: int = int(os.environ.get("MAX_ITERATIONS", "10"))
        self.documents_base_path: str = os.environ.get(
            "DOCUMENTS_BASE_PATH", "documents"
        )

        self._validate()

    def _validate(self) -> None:
        """Prüft, ob alle Pflichtfelder gesetzt sind, und loggt Warnungen."""
        if not self.azure_openai_endpoint:
            logger.warning(
                "AZURE_OPENAI_ENDPOINT ist nicht gesetzt. "
                "Bitte .env-Datei nach .env.example erstellen."
            )
        if not self.azure_openai_api_key:
            logger.warning(
                "AZURE_OPENAI_API_KEY ist nicht gesetzt. "
                "Bitte .env-Datei nach .env.example erstellen."
            )
