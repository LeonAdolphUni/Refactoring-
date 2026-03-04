"""RAG-Agent – KI-Logik, Indexierung und iterative Suchschleife.

Nutzt Azure OpenAI mit Structured Outputs (OpenAI Python SDK),
um relevante Kapitel auszuwählen und Antworten zu extrahieren.
"""

import logging
import time
from typing import Any, Optional

import httpx
from openai import AzureOpenAI
from pydantic import BaseModel, Field

from src.config import Config
from src.toolset import PDFReader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Models für Structured Outputs
# ---------------------------------------------------------------------------


class ChapterSummary(BaseModel):
    """Zusammenfassung eines einzelnen Kapitels."""

    title: str
    summary: str = Field(description="1-2 Satz Zusammenfassung des Kapitelinhalts")
    level: int


class ChapterSelection(BaseModel):
    """Auswahl der relevantesten Kapitel für eine Frage."""

    selected_chapters: list[str] = Field(
        description="Liste der ausgewählten Kapitel-Titel"
    )
    reasoning: str = Field(description="Begründung für die Auswahl")


class AnswerResult(BaseModel):
    """Ergebnis der Antwortsuche in einem Kapitel."""

    found: bool = Field(description="True wenn die Antwort im Text gefunden wurde")
    answer: Optional[str] = Field(
        default=None, description="Die formulierte Antwort"
    )
    reasoning: Optional[str] = Field(
        default=None, description="Begründung der Antwort mit Textbelegen"
    )
    source_chapters: list[str] = Field(
        default_factory=list,
        description="Kapitel aus denen die Antwort stammt",
    )


# ---------------------------------------------------------------------------
# RAGAgent
# ---------------------------------------------------------------------------


class RAGAgent:
    """Steuert die KI-Logik, den Kapitel-Index und die iterative Suche.

    Alle LLM-Aufrufe laufen über ``_call_llm`` und sind mit einem harten
    Timeout abgesichert. Token-Usage wird pro Aufruf extrahiert und
    akkumuliert.
    """

    def __init__(self, config: Config, reader: PDFReader) -> None:
        """Initialisiert den RAGAgent.

        Args:
            config: Konfigurationsobjekt mit Azure-OpenAI-Einstellungen.
            reader: PDFReader-Instanz für das Einlesen der Dokumente.
        """
        self.config = config
        self.reader = reader
        self._current_index: str = ""

        self._client = AzureOpenAI(
            azure_endpoint=config.azure_openai_endpoint,
            api_key=config.azure_openai_api_key,
            api_version=config.azure_openai_api_version,
            timeout=httpx.Timeout(float(config.llm_timeout)),
        )
        logger.info(
            "AzureOpenAI-Client initialisiert (Deployment: %s, Timeout: %ds).",
            config.azure_openai_deployment,
            config.llm_timeout,
        )

    # ------------------------------------------------------------------
    # Interner LLM-Wrapper
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        messages: list[dict],
        response_model: type[BaseModel] | None = None,
    ) -> tuple[Any, dict]:
        """Wrapper für alle LLM-Aufrufe mit Timeout und Token-Tracking.

        Wenn ``response_model`` angegeben ist, wird OpenAI Structured Output
        (``beta.chat.completions.parse``) verwendet und das Ergebnis als
        Instanz des Pydantic-Modells zurückgegeben. Andernfalls wird der
        Rohtext der Antwort zurückgegeben.

        Args:
            messages: Liste von OpenAI Chat-Message-Dictionaries.
            response_model: Optionales Pydantic-Modell für Structured Output.

        Returns:
            Tuple aus (geparste Antwort oder Rohtext, Token-Usage-Dictionary).
            Das Token-Usage-Dictionary hat die Schlüssel
            ``prompt_tokens`` und ``completion_tokens``.

        Raises:
            Keine – Fehler werden intern abgefangen und geloggt.
            Bei einem Fehler wird ``(None, {"prompt_tokens": 0,
            "completion_tokens": 0})`` zurückgegeben.
        """
        usage_empty: dict = {"prompt_tokens": 0, "completion_tokens": 0}
        try:
            if response_model is not None:
                response = self._client.beta.chat.completions.parse(
                    model=self.config.azure_openai_deployment,
                    messages=messages,  # type: ignore[arg-type]
                    response_format=response_model,
                )
                parsed = response.choices[0].message.parsed
                usage = response.usage
                token_info = {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                }
                return parsed, token_info
            else:
                response = self._client.chat.completions.create(
                    model=self.config.azure_openai_deployment,
                    messages=messages,  # type: ignore[arg-type]
                )
                text = response.choices[0].message.content or ""
                usage = response.usage
                token_info = {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                }
                return text, token_info

        except httpx.TimeoutException as exc:
            logger.error(
                "LLM-Timeout nach %ds: %s", self.config.llm_timeout, exc
            )
            return None, usage_empty
        except Exception as exc:
            logger.error("LLM-Fehler: %s", exc)
            return None, usage_empty

    # ------------------------------------------------------------------
    # Index-Erstellung
    # ------------------------------------------------------------------

    def build_index(self, filename: str) -> str:
        """Erstellt einen Markdown-Kapitel-Index für ein PDF-Dokument.

        Für jedes Kapitel wird ein LLM-Aufruf durchgeführt, um eine
        1-2-Satz-Zusammenfassung zu generieren. Der resultierende
        Markdown-Index wird als Attribut ``_current_index`` gespeichert.

        Args:
            filename: Pfad zur PDF-Datei.

        Returns:
            Markdown-Index als String.
        """
        chapters = self.reader.get_chapters_structured(filename)
        if not chapters:
            logger.warning(
                "Keine Kapitel gefunden in '%s'. Index ist leer.", filename
            )
            self._current_index = ""
            return ""

        import os

        basename = os.path.basename(filename)
        index_lines: list[str] = [f"## Kapitel-Index für {basename}", ""]

        total_prompt_tokens = 0
        total_completion_tokens = 0

        for chapter in chapters:
            title = chapter.get("title", "Unbekannt")
            content = chapter.get("content", "")

            prompt = (
                "Fasse den folgenden Kapiteltext in 1-2 Sätzen zusammen. "
                "Antworte nur mit der Zusammenfassung.\n\n"
                f"Kapitel: {title}\n"
                f"Text: {content[:2000]}"
            )
            messages = [{"role": "user", "content": prompt}]

            summary_text, token_info = self._call_llm(messages)
            total_prompt_tokens += token_info["prompt_tokens"]
            total_completion_tokens += token_info["completion_tokens"]

            summary = summary_text if summary_text else "(Keine Zusammenfassung verfügbar)"

            index_lines.append(f"### {title}")
            index_lines.append(f"**Zusammenfassung:** {summary}")
            index_lines.append("")

        logger.info(
            "Index erstellt für '%s': %d Kapitel, %d Prompt-Tokens, "
            "%d Completion-Tokens.",
            basename,
            len(chapters),
            total_prompt_tokens,
            total_completion_tokens,
        )

        self._current_index = "\n".join(index_lines)
        return self._current_index

    # ------------------------------------------------------------------
    # Frage-Antwort-Schleife
    # ------------------------------------------------------------------

    def ask(self, filename: str, question: str, index: str) -> dict:
        """Sucht iterativ eine Antwort auf eine Frage in einem Dokument.

        Wählt in jeder Iteration via LLM die relevantesten Kapitel aus,
        liest deren Volltext und prüft, ob die Frage beantwortet werden
        kann. Bereits geprüfte Kapitel werden auf eine Blacklist gesetzt,
        um Endlosschleifen zu verhindern.

        Args:
            filename: Pfad zur PDF-Datei.
            question: Die zu beantwortende Frage.
            index: Markdown-Kapitel-Index (aus ``build_index``).

        Returns:
            Dictionary mit den Schlüsseln ``frage``, ``antwort``,
            ``begruendung``, ``quellen``, ``dauer_sekunden``,
            ``prompt_tokens``, ``completion_tokens``, ``total_tokens``
            und ``iterationen``.
        """
        total_prompt_tokens = 0
        total_completion_tokens = 0
        start_time = time.time()
        blacklisted_chapters: list[str] = []
        final_answer: str = "Nicht gefunden"
        final_reasoning: str = ""
        final_sources: list[str] = []
        iteration = 0

        for iteration in range(1, self.config.max_iterations + 1):
            logger.info(
                "Iteration %d/%d für Frage: '%s'",
                iteration,
                self.config.max_iterations,
                question[:80],
            )

            # ----------------------------------------------------------
            # Schritt 1: Kapitel-Auswahl via LLM
            # ----------------------------------------------------------
            blacklist_hint = (
                f"\nWICHTIG: Wähle KEINE Kapitel aus dieser Blacklist: "
                f"{blacklisted_chapters}"
                if blacklisted_chapters
                else ""
            )
            selection_prompt = (
                "Gegeben ist folgender Kapitel-Index eines Dokuments und eine Frage.\n"
                "Wähle die 1-3 relevantesten Kapitel aus, die die Frage beantworten könnten."
                f"{blacklist_hint}\n\n"
                f"Kapitel-Index:\n{index}\n\n"
                f"Frage: {question}\n\n"
                "Antworte im JSON-Format mit selected_chapters und reasoning."
            )
            selection_messages = [
                {"role": "user", "content": selection_prompt}
            ]
            selection_result, token_info = self._call_llm(
                selection_messages, response_model=ChapterSelection
            )
            total_prompt_tokens += token_info["prompt_tokens"]
            total_completion_tokens += token_info["completion_tokens"]

            # ----------------------------------------------------------
            # Schritt 2: Abbruchbedingung
            # ----------------------------------------------------------
            if selection_result is None or not selection_result.selected_chapters:
                logger.info(
                    "Keine weiteren Kapitel ausgewählt. Suche beendet."
                )
                break

            selected_chapters = selection_result.selected_chapters
            logger.info("Ausgewählte Kapitel: %s", selected_chapters)

            # ----------------------------------------------------------
            # Schritt 3: Volltexte holen
            # ----------------------------------------------------------
            combined_text_parts: list[str] = []
            for chapter_title in selected_chapters:
                content = self.reader.get_chapter_content(
                    filename, chapter_title
                )
                if content:
                    combined_text_parts.append(
                        f"### {chapter_title}\n{content}"
                    )

            combined_text = "\n\n".join(combined_text_parts)

            if not combined_text.strip():
                logger.warning(
                    "Kapitel-Inhalt für %s leer. Überspringe Iteration.",
                    selected_chapters,
                )
                blacklisted_chapters.extend(selected_chapters)
                continue

            # ----------------------------------------------------------
            # Schritt 4: Antwort-Versuch via LLM
            # ----------------------------------------------------------
            answer_prompt = (
                "Beantwortet der folgende Text die Frage?\n"
                "Wenn JA: Setze found=True und formuliere eine vollständige "
                "Antwort mit Begründung.\n"
                "Wenn NEIN: Setze found=False.\n\n"
                f"Text: {combined_text[:4000]}\n\n"
                f"Frage: {question}"
            )
            answer_messages = [{"role": "user", "content": answer_prompt}]
            answer_result, token_info = self._call_llm(
                answer_messages, response_model=AnswerResult
            )
            total_prompt_tokens += token_info["prompt_tokens"]
            total_completion_tokens += token_info["completion_tokens"]

            # ----------------------------------------------------------
            # Schritt 5: Ergebnis prüfen
            # ----------------------------------------------------------
            if answer_result is not None and answer_result.found:
                final_answer = answer_result.answer or "Nicht gefunden"
                final_reasoning = answer_result.reasoning or ""
                final_sources = answer_result.source_chapters or selected_chapters
                logger.info("Antwort gefunden in Iteration %d.", iteration)
                break

            # Kapitel auf Blacklist setzen und weiter suchen
            blacklisted_chapters.extend(selected_chapters)
            logger.info(
                "Antwort nicht gefunden. Kapitel auf Blacklist: %s",
                blacklisted_chapters,
            )

        else:
            logger.info(
                "Maximale Iterationsanzahl (%d) erreicht ohne Antwort.",
                self.config.max_iterations,
            )

        duration = round(time.time() - start_time, 2)
        return {
            "frage": question,
            "antwort": final_answer,
            "begruendung": final_reasoning,
            "quellen": final_sources,
            "dauer_sekunden": duration,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "iterationen": iteration,
        }
