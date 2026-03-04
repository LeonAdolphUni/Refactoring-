"""Test-Orchestrator für das RAG-System.

Führt automatisierte Tests mit 5 Dokumenten (je 10 Fragen) durch
und speichert die Ergebnisse als Excel-Dateien.
"""

import glob
import logging
import os

import pandas as pd

from src.agent import RAGAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Generische Testfragen für 5 Dokumente
# ---------------------------------------------------------------------------

TEST_QUESTIONS: dict[int, list[str]] = {
    1: [
        "Was ist das Hauptthema des Dokuments?",
        "Welche Methodik wird im Dokument beschrieben?",
        "Was sind die zentralen Ergebnisse?",
        "Welche Schlussfolgerungen werden gezogen?",
        "Wer sind die Autoren oder verantwortlichen Personen?",
        "Welche Limitationen oder Einschränkungen werden genannt?",
        "Welcher theoretische Rahmen wird verwendet?",
        "Welche Datenquellen oder Referenzen werden genutzt?",
        "Was sind die praktischen Implikationen?",
        "Welche zukünftigen Forschungsrichtungen werden vorgeschlagen?",
    ],
    2: [
        "Worum geht es in diesem Dokument hauptsächlich?",
        "Welche Vorgehensweise wird beschrieben?",
        "Welche Kernaussagen enthält das Dokument?",
        "Was wird als Fazit formuliert?",
        "Welche Personen oder Organisationen werden erwähnt?",
        "Welche Risiken oder Probleme werden thematisiert?",
        "Auf welchen Grundlagen basiert das Dokument?",
        "Welche Quellen werden im Dokument zitiert?",
        "Welche Handlungsempfehlungen werden gegeben?",
        "Welche offenen Fragen bleiben bestehen?",
    ],
    3: [
        "Was ist die zentrale Fragestellung des Dokuments?",
        "Welche Analysemethoden kommen zum Einsatz?",
        "Welche Hauptergebnisse werden präsentiert?",
        "Wie lautet das Gesamtfazit?",
        "Welche Stakeholder werden identifiziert?",
        "Welche Herausforderungen werden beschrieben?",
        "Welche Modelle oder Frameworks werden angewendet?",
        "Welche empirischen Daten werden herangezogen?",
        "Welche Empfehlungen werden ausgesprochen?",
        "Welche Trends oder Entwicklungen werden prognostiziert?",
    ],
    4: [
        "Was behandelt dieses Dokument im Kern?",
        "Welches Verfahren wird zur Untersuchung genutzt?",
        "Was sind die wichtigsten Befunde?",
        "Welche Zusammenfassung wird am Ende gegeben?",
        "Welche Akteure spielen eine Rolle?",
        "Welche Schwachstellen werden identifiziert?",
        "Welche wissenschaftlichen Theorien werden herangezogen?",
        "Welche statistischen Daten werden präsentiert?",
        "Welche konkreten Maßnahmen werden vorgeschlagen?",
        "Welche Perspektiven für die Zukunft werden aufgezeigt?",
    ],
    5: [
        "Was ist der Hauptgegenstand des Dokuments?",
        "Welche Untersuchungsmethoden werden verwendet?",
        "Welche Ergebnisse sind besonders hervorzuheben?",
        "Was ist die abschließende Bewertung?",
        "Welche Institutionen oder Experten werden genannt?",
        "Welche Grenzen der Untersuchung werden diskutiert?",
        "Auf welchem konzeptionellen Rahmen baut das Dokument auf?",
        "Welche Beispiele oder Fallstudien werden angeführt?",
        "Welche Strategien werden empfohlen?",
        "Welche weiterführenden Themen werden angesprochen?",
    ],
}


# ---------------------------------------------------------------------------
# Test-Orchestrator
# ---------------------------------------------------------------------------


def run_tests(agent: RAGAgent) -> None:
    """Führt automatisierte Tests mit 5 Dokumenten (je 10 Fragen) durch.

    Für jedes Dokument wird ein Kapitel-Index erstellt und anschließend
    10 vordefinierte Fragen gestellt. Ergebnisse werden in der Konsole
    ausgegeben und als Excel-Dateien gespeichert.

    Args:
        agent: Initialisierter RAGAgent.
    """
    all_results: list[dict] = []

    for doc_num in range(1, 6):
        folder = os.path.join(
            agent.config.documents_base_path, f"document{doc_num}"
        )

        # PDF finden
        pdf_files = glob.glob(os.path.join(folder, "*.pdf"))
        if not pdf_files:
            print(f"⚠️  Keine PDF in {folder} gefunden, überspringe...")
            logger.warning("Keine PDF in '%s' gefunden.", folder)
            continue
        pdf_file = pdf_files[0]

        print(f"\n{'='*60}")
        print(f"📄 Dokument {doc_num}: {os.path.basename(pdf_file)}")
        print(f"{'='*60}")
        logger.info("Verarbeite Dokument %d: %s", doc_num, pdf_file)

        # Index generieren
        print("🔨 Generiere Index...")
        index = agent.build_index(pdf_file)
        print(f"✅ Index erstellt ({len(index)} Zeichen)")

        # Fragen stellen
        doc_results: list[dict] = []
        questions = TEST_QUESTIONS.get(doc_num, [])
        for i, question in enumerate(questions, 1):
            print(f"\n--- Frage {i}/10 ---")
            result = agent.ask(pdf_file, question, index)

            # Statistiken in Konsole ausgeben
            print(f"❓ Frage: {result['frage']}")
            antwort_preview = (
                result["antwort"][:200] + "..."
                if len(result["antwort"]) > 200
                else result["antwort"]
            )
            print(f"✅ Antwort: {antwort_preview}")
            print(f"⏱️  Dauer: {result['dauer_sekunden']:.2f}s")
            print(
                f"🔢 Tokens: {result['total_tokens']} "
                f"(Prompt: {result['prompt_tokens']}, "
                f"Completion: {result['completion_tokens']})"
            )
            print(
                f"📚 Quellen: "
                f"{', '.join(result['quellen']) if result['quellen'] else 'Keine'}"
            )
            print(f"🔄 Iterationen: {result['iterationen']}")

            doc_results.append(result)

        # Zusammenfassung pro Dokument
        if doc_results:
            print(f"\n{'='*60}")
            print(f"📊 Zusammenfassung Dokument {doc_num}")
            print(f"{'='*60}")
            avg_time = (
                sum(r["dauer_sekunden"] for r in doc_results) / len(doc_results)
            )
            total_tokens = sum(r["total_tokens"] for r in doc_results)
            found_count = sum(
                1 for r in doc_results if r["antwort"] != "Nicht gefunden"
            )
            print(f"   Durchschn. Dauer: {avg_time:.2f}s")
            print(f"   Gesamt-Tokens: {total_tokens}")
            print(f"   Gefundene Antworten: {found_count}/{len(doc_results)}")

            # Als Excel speichern
            df = pd.DataFrame(doc_results)
            excel_path = f"Auswertung_Doc{doc_num}.xlsx"
            df.to_excel(excel_path, index=False)
            print(f"💾 Ergebnisse gespeichert: {excel_path}")
            logger.info("Ergebnisse für Dokument %d gespeichert: %s", doc_num, excel_path)

        all_results.extend(doc_results)

    # Gesamtstatistik
    if all_results:
        print(f"\n{'='*60}")
        print("📊 GESAMTSTATISTIK")
        print(f"{'='*60}")
        total_questions = len(all_results)
        total_found = sum(
            1 for r in all_results if r["antwort"] != "Nicht gefunden"
        )
        total_time = sum(r["dauer_sekunden"] for r in all_results)
        total_all_tokens = sum(r["total_tokens"] for r in all_results)
        print(f"   Fragen gesamt: {total_questions}")
        print(f"   Antworten gefunden: {total_found}/{total_questions}")
        print(f"   Gesamtdauer: {total_time:.2f}s")
        print(
            f"   Durchschn. Dauer pro Frage: "
            f"{total_time / total_questions:.2f}s"
        )
        print(f"   Gesamt-Tokens: {total_all_tokens}")

        # Gesamt-Excel
        df_all = pd.DataFrame(all_results)
        df_all.to_excel("Auswertung_Gesamt.xlsx", index=False)
        print("💾 Gesamtergebnisse gespeichert: Auswertung_Gesamt.xlsx")
        logger.info("Gesamtergebnisse gespeichert: Auswertung_Gesamt.xlsx")
