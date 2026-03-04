"""Test-Orchestrator für das RAG-System.

Führt automatisierte Tests mit 5 Dokumenten (je 10 Fragen) durch
und speichert die Ergebnisse als Excel-Dateien.
"""

import glob
import logging
import os
import re

import pandas as pd
from tqdm import tqdm

from src.agent import RAGAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Generische Testfragen für 5 Dokumente
# ---------------------------------------------------------------------------

TEST_QUESTIONS: dict[int, list[str]] = {
    1: [
        "Bis zu welchem Datum endet die Frist für das Stellen von Bieterfragen? (Antwort im Format TT.MM.JJJJ)",
        "An welchen Standort wird das RZF NRW ab voraussichtlich 2026 verlegt?",
        "Wie viele Bewertungspunkte gibt es in Los 1 für die Zertifizierung 'ISTQB – Advanced Level Test Analyst'?",
        "Wie lautet die Mindestanforderung an die Jahre Java-Erfahrung für das Personal in Los 16 im Vergleich zu Los 9?",
        "Welche Framework-/Technologiekenntnisse werden in Los 16 in den Bewertungskriterien genannt? Nennen Sie mindestens 5 konkrete Beispiele.",
        "Ist für Los 28 eine Sicherheitsüberprüfung nach SÜG NW erforderlich?",
        "Welche Konsequenz wird genannt, wenn Sicherheitserklärungen nicht binnen zwei Wochen nach Aufforderung eingereicht werden?",
        "Wie hoch ist die maximal erreichbare Gesamtpunktzahl (Gesamtsumme) der Zuschlagskriterien in Los 37?",
        "Sind Nebenangebote zugelassen?",
        "Wie ist die Rolle des Repräsentanten definiert, und unter welcher Bedingung darf diese Rolle auch operativ tätig sein?",
    ],
    2: [
        "Wofür steht die Abkürzung 'DIPSY' im Kontext dieses Dokuments?",
        "An welchem Standort finden die Termine für das Technische Consulting zur Sicherstellung der Kommunikationsqualität statt?",
        "Nennen Sie die Mindestanforderung an die Erfahrung in der Leitung großer Softwareprojekte für die Rolle 'Projektleiter/-in'.",
        "Welche spezifischen Zertifizierungen sind für die Rolle 'Berater Datenschutz und Informationssicherheit' zwingend erforderlich? Nennen Sie zwei.",
        "Welches Web-Framework wird spezifisch für das Modul 'Notenerfassung Online (NEO)' eingesetzt?",
        "Welches Datenbanksystem wird sowohl für 'ASV-BW' als auch für 'NEO' verwendet?",
        "Was ist die Konsequenz, wenn ein Bieter die definierten Mindestanforderungen (Ausschlusskriterien) für eine Rolle nicht erfüllt?",
        "Wer ist für den Betrieb und die Absicherung des Landesverwaltungsnetzes (LVN) zuständig?",
        "In welchem Zeitraum findet die Statistik-Erhebung 'Prognose' statt?",
        "Vergleichen Sie die geforderte Mindest-Berufserfahrung des 'Projektleiter/-in' mit der des 'IT-Architekt/-in' im Bereich Softwareentwicklung.",
    ],
    3: [
        "Which container orchestration technology is explicitly required for the EMP infrastructure?",
        "What is the 'Price Sheet Category' defined for the 'Software Architect' role?",
        "List the five external API Collections provided by the EMP Backend.",
        "Compare the annual uptime target for the Production environment versus the Non-production environments.",
        "Which specific Product Team is responsible for the 'Enablement Hub' frontend?",
        "What is the minimum professional experience required for the 'Frontend Engineer' role?",
        "Under what condition can a performance-based bonus be granted regarding test coverage?",
        "What are the three core principles/objectives of the 'Transparency Hub'?",
        "How is the term 'Intermediary' defined in the Glossary?",
        "What is the duration of the 'EMP 0.9 Phase' and what is its primary goal regarding onboarding?",
    ],
    4: [
        "Wann ist der Leistungsbeginn für 'Los 2' gemäß der Zeitplanung? (Antwort im Format TT.MM.JJJJ)",
        "Wie hoch ist die vereinbarte 'Mindestabnahme (PT)' für Los 2 im Jahr 2029?",
        "Wie groß darf das Kernteam für 'Los 2' maximal sein?",
        "Welche spezifische BSI-Personenzertifizierung wird für den 'Vorfall-Experten' im Kernteam von Los 1 verlangt?",
        "Vergleichen Sie den Leistungsbeginn von 'Los 1' mit dem von 'Los 3'.",
        "Ist für das eingesetzte Personal im 'Los 4' (Schulungen) eine Sicherheitsüberprüfung erforderlich?",
        "Unter welcher Bedingung müssen sich Experten einer 'erweiterten Sicherheitsüberprüfung (Ü 2)' unterziehen?",
        "Auf welcher ISO-Normenfamilie muss die strategische Entwicklung der BCM-Strategie in Los 1 basieren?",
        "Wer fungiert gemäß dem Rollenmodell als 'Vertrags-Owner' auf Seiten des Auftraggebers?",
        "Welche Zertifizierung ist für den Auftragnehmer in Los 3 (Sicherheitsbewertung) zwingend erforderlich?",
    ],
    5: [
        "Bis zu welchem Datum und welcher Uhrzeit müssen die Angebote spätestens eingegangen sein (Angebotsfrist)?",
        "Welche Gewichtung (%) entfällt bei der Zuschlagsentscheidung auf den Preis und welche auf die Leistung (Qualität)?",
        "Welches Sprachniveau (GER) wird für den Datenschutzbeauftragten (DSB) zwingend vorausgesetzt?",
        "Vergleichen Sie die geschätzte Abnahmemenge (Stunden pro Jahr) für die laufenden Tätigkeiten des 'DSB' mit denen des 'DSK-Teams'.",
        "Welche Mindestdeckungssumme für Personenschäden muss die Berufshaftpflichtversicherung gemäß Formblatt 03 aufweisen?",
        "Nennen Sie die zwei Departments der UTN, die in der Leistungsbeschreibung erwähnt werden, um die interdisziplinäre Ausrichtung zu beschreiben.",
        "Ab welchem Datum darf eine Preisanpassung (Vergütungserhöhung) frühestens erfolgen?",
        "Sind Nebenangebote in diesem Verfahren zugelassen?",
        "Welche konkrete Aufgabe hat das DSK-Team (Datenschutzkoordinatoren) in Bezug auf Betroffenenanfragen (Art. 15-21 DSGVO)?",
        "Wie viele Punkte können maximal im Wertungskriterium 'Fachliche Qualifikation und Erfahrung' erreicht werden (ungewichtet)?",
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

        # Index-Speicherpfad anzeigen
        pdf_stem = os.path.splitext(os.path.basename(pdf_file))[0]
        safe_name = re.sub(r"[^\w]", "_", pdf_stem)
        doc_folder = os.path.basename(os.path.dirname(pdf_file))
        index_path = f"results/index_{doc_folder}_{safe_name}.md"
        print(f"📝 Index gespeichert: {index_path}")

        # Fragen stellen
        doc_results: list[dict] = []
        questions = TEST_QUESTIONS.get(doc_num, [])
        for i, question in enumerate(
            tqdm(questions, desc=f"📄 Dokument {doc_num}", unit="Fragen"), 1
        ):
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
