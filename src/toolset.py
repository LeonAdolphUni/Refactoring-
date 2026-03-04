"""PDFReader – Einlesen und Cachen von PDF-Dokumenten mit Docling.

Stellt eine einfache Schnittstelle zum Parsen von PDFs und zum Zugriff
auf einzelne Kapitel bereit. Parsed jede Datei nur einmal (In-Memory-Cache).
"""

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PDFReader:
    """Liest PDF-Dokumente mit Docling ein und cached die Ergebnisse im RAM.

    Der In-Memory-Cache ``chapter_cache`` speichert die extrahierte
    Kapitelstruktur jeder Datei nach dem ersten Parsen. So wird Docling
    für jede Frage nicht erneut aufgerufen.
    """

    def __init__(self) -> None:
        """Initialisiert den PDFReader und den leeren Kapitel-Cache."""
        self.chapter_cache: dict[str, list[dict]] = {}
        self._converter = self._create_converter()

    # ------------------------------------------------------------------
    # Interne Hilfsmethoden
    # ------------------------------------------------------------------

    @staticmethod
    def _create_converter() -> "Optional[Any]":
        """Erzeugt einen Docling DocumentConverter mit RAM-schonenden Optionen.

        OCR und Seiten-Bild-Generierung sind deaktiviert, um den
        Speicherverbrauch auf Firmen-Laptops zu minimieren.

        Returns:
            Einen initialisierten ``DocumentConverter`` oder ``None`` bei Fehler.
        """
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            pipeline_options = PdfPipelineOptions(
                do_ocr=False,
                do_table_structure=False,
                generate_page_images=False,
            )
            return DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        except ImportError:
            try:
                from docling.document_converter import DocumentConverter

                logger.warning(
                    "PdfFormatOption nicht verfügbar. "
                    "Fallback auf DocumentConverter() ohne RAM-Schutz-Optionen."
                )
                return DocumentConverter()
            except Exception as exc:
                logger.error("Docling konnte nicht initialisiert werden: %s", exc)
                return None
        except Exception as exc:
            logger.error("Docling konnte nicht initialisiert werden: %s", exc)
            return None

    @staticmethod
    def _extract_chapters(doc: Any) -> list[dict]:
        """Zerlegt ein Docling-Dokument anhand von Überschriften in Kapitel.

        Args:
            doc: Das von Docling geparste Dokument-Objekt.

        Returns:
            Liste von Kapitel-Dictionaries mit den Schlüsseln
            ``title``, ``content`` und ``level``.
        """
        chapters: list[dict] = []
        current_chapter: Optional[dict] = None
        current_content_parts: list[str] = []

        try:
            for item, _ in doc.iterate_items():
                item_type = type(item).__name__

                if item_type == "SectionHeaderItem":
                    # Vorheriges Kapitel abschließen
                    if current_chapter is not None:
                        current_chapter["content"] = "\n".join(
                            current_content_parts
                        ).strip()
                        chapters.append(current_chapter)

                    # Neues Kapitel beginnen
                    level = getattr(item, "level", 1)
                    current_chapter = {
                        "title": item.text.strip(),
                        "content": "",
                        "level": level,
                    }
                    current_content_parts = []

                elif item_type in ("TextItem", "TableItem", "ListItem"):
                    text = getattr(item, "text", "")
                    if text:
                        current_content_parts.append(text)

            # Letztes Kapitel abschließen
            if current_chapter is not None:
                current_chapter["content"] = "\n".join(
                    current_content_parts
                ).strip()
                chapters.append(current_chapter)

            # Falls keine Überschriften gefunden: gesamten Text als
            # ein einziges Kapitel zurückgeben
            if not chapters:
                all_text_parts: list[str] = []
                for item, _ in doc.iterate_items():
                    text = getattr(item, "text", "")
                    if text:
                        all_text_parts.append(text)
                if all_text_parts:
                    chapters.append(
                        {
                            "title": "Gesamtdokument",
                            "content": "\n".join(all_text_parts).strip(),
                            "level": 1,
                        }
                    )

        except Exception as exc:
            logger.warning(
                "Fehler beim Extrahieren der Kapitel: %s", exc
            )

        return chapters

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def _parse_with_pypdf(self, filename: str) -> list[dict]:
        """Fallback-Parser mit pypdf für große PDFs die Docling nicht verarbeiten kann.

        Args:
            filename: Pfad zur PDF-Datei.

        Returns:
            Liste von Kapitel-Dictionaries mit den Schlüsseln
            ``title``, ``content`` und ``level``.
        """
        logger.warning("Verwende PyPDF-Fallback für '%s'.", filename)
        try:
            from pypdf import PdfReader as PyPdfReader

            reader = PyPdfReader(filename)
            chapters: list[dict] = []
            current_title = "Abschnitt 1"
            current_content_parts: list[str] = []
            all_page_texts: list[str] = []

            for page in reader.pages:
                text = page.extract_text() or ""
                all_page_texts.append(text)
                lines = text.split("\n")

                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue

                    # Heuristik: Zeile ist eine Überschrift wenn:
                    # - Kurz (< 100 Zeichen) UND
                    # - Beginnt mit einer Nummer (z.B. "1.", "1.1", "2.3.1") ODER
                    # - Ist komplett in Großbuchstaben
                    is_heading = False
                    if len(stripped) < 100:
                        if re.match(r'^\d+(\.\d+)*\.?\s+\S', stripped):
                            is_heading = True
                        elif stripped.isupper() and len(stripped) > 3:
                            is_heading = True

                    if is_heading:
                        # Vorheriges Kapitel abschließen
                        if current_content_parts:
                            chapters.append({
                                "title": current_title,
                                "content": "\n".join(current_content_parts).strip(),
                                "level": 1,
                            })
                        current_title = stripped
                        current_content_parts = []
                    else:
                        current_content_parts.append(stripped)

            # Letztes Kapitel abschließen
            if current_content_parts:
                chapters.append({
                    "title": current_title,
                    "content": "\n".join(current_content_parts).strip(),
                    "level": 1,
                })

            # Wenn keine Kapitel erkannt: gesamten Text als ein Kapitel
            if not chapters and all_page_texts:
                chapters.append({
                    "title": "Gesamtdokument",
                    "content": "\n".join(all_page_texts).strip(),
                    "level": 1,
                })

            logger.info(
                "PyPDF-Fallback: %d Kapitel erkannt in '%s'.", len(chapters), filename
            )
            return chapters

        except Exception as exc:
            logger.error("PyPDF-Fallback fehlgeschlagen für '%s': %s", filename, exc)
            return []

    def get_chapters_structured(self, filename: str) -> list[dict]:
        """Parst eine PDF-Datei und gibt die Kapitelstruktur zurück.

        Beim ersten Aufruf wird die Datei mit Docling geparst und das
        Ergebnis im ``chapter_cache`` gespeichert. Nachfolgende Aufrufe
        geben die gecachten Daten zurück.

        Args:
            filename: Pfad zur PDF-Datei.

        Returns:
            Liste von Kapitel-Dictionaries mit ``title``, ``content``
            und ``level``. Bei Fehlern wird eine leere Liste zurückgegeben.
        """
        if filename in self.chapter_cache:
            logger.debug("Cache-Treffer für '%s'.", filename)
            return self.chapter_cache[filename]

        if self._converter is None:
            logger.warning(
                "Docling-Converter nicht verfügbar. Wechsle zu PyPDF-Fallback."
            )
            chapters = self._parse_with_pypdf(filename)
            self.chapter_cache[filename] = chapters
            return chapters

        logger.info("Parse PDF: '%s' …", filename)
        try:
            from tqdm import tqdm

            with tqdm(
                total=1,
                desc="Parsing PDF",
                bar_format="{desc}: {bar} {percentage:.0f}%",
                ncols=50,
            ) as pbar:
                result = self._converter.convert(filename)
                pbar.update(1)
            doc = result.document
            chapters = self._extract_chapters(doc)

            # Fallback wenn Docling keine brauchbaren Kapitel liefert
            if not chapters or all(not ch.get("content") for ch in chapters):
                logger.warning(
                    "Docling lieferte keine Kapitel mit Inhalt für '%s'. "
                    "Wechsle zu PyPDF-Fallback.",
                    filename,
                )
                chapters = self._parse_with_pypdf(filename)

            self.chapter_cache[filename] = chapters
            logger.info(
                "PDF geparst: %d Kapitel gefunden in '%s'.",
                len(chapters),
                filename,
            )
            return chapters
        except Exception as exc:
            logger.warning(
                "Docling fehlgeschlagen für '%s': %s. Wechsle zu PyPDF-Fallback.",
                filename,
                exc,
            )
            chapters = self._parse_with_pypdf(filename)
            self.chapter_cache[filename] = chapters
            return chapters

    def get_chapter_content(self, filename: str, chapter_title: str) -> str:
        """Gibt den Volltext eines Kapitels zurück.

        Sucht case-insensitiv nach dem Kapitel-Titel in der gecachten
        (oder frisch geparsten) Kapitelstruktur der angegebenen Datei.

        Args:
            filename: Pfad zur PDF-Datei.
            chapter_title: Titel des gesuchten Kapitels.

        Returns:
            Volltext des Kapitels als String. Leerer String, wenn das
            Kapitel nicht gefunden wurde.
        """
        chapters = self.get_chapters_structured(filename)
        title_lower = chapter_title.lower()
        for chapter in chapters:
            if chapter.get("title", "").lower() == title_lower:
                return chapter.get("content", "")
        logger.debug(
            "Kapitel '%s' nicht in '%s' gefunden.", chapter_title, filename
        )
        return ""
