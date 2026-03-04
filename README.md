# Modulares RAG-System für intelligente PDF-Analyse

Dieses Projekt implementiert ein vollständiges, modulares **RAG (Retrieval-Augmented Generation) System** für die intelligente Analyse von PDF-Dokumenten. Es liest komplexe PDFs ein, erstellt einen intelligenten Kapitel-Index, wählt via Azure OpenAI relevante Abschnitte aus und iteriert so lange, bis eine Antwort gefunden wurde.

---

## Architektur-Übersicht

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│          (Einstiegspunkt + HF Symlink-Fix)                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
          ┌─────────────▼─────────────┐
          │        tester.py          │
          │   (Test-Orchestrator)     │
          │   5 PDFs × 10 Fragen      │
          └─────────────┬─────────────┘
                        │
          ┌─────────────▼─────────────┐
          │      src/agent.py         │
          │      (RAGAgent)           │
          │  ┌────────────────────┐   │
          │  │  build_index()     │   │
          │  │  ask()             │   │
          │  │  _call_llm()       │   │
          │  └────────────────────┘   │
          └──────┬────────────┬───────┘
                 │            │
   ┌─────────────▼──┐   ┌────▼──────────────┐
   │ src/toolset.py │   │  Azure OpenAI API  │
   │  (PDFReader)   │   │  (gpt-4o)          │
   │ ┌────────────┐ │   └────────────────────┘
   │ │  Docling   │ │
   │ │  + Cache   │ │
   │ └────────────┘ │
   └────────────────┘
          │
   ┌──────▼──────┐
   │ src/config.py│
   │ (Config)     │
   └─────────────┘
```

---

## Voraussetzungen

- **Python 3.10+**
- **Azure OpenAI** Zugang (Endpoint, API Key, Deployment-Name)
- Ausreichend RAM (empfohlen: mind. 8 GB; OCR ist deaktiviert)

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Konfiguration

1. Erstelle eine `.env`-Datei im Projektverzeichnis (Vorlage: `.env.example`):

```bash
cp .env.example .env
```

2. Trage deine Azure OpenAI Zugangsdaten ein:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_DEPLOYMENT=gpt-4o
LLM_TIMEOUT=30
MAX_ITERATIONS=10
DOCUMENTS_BASE_PATH=documents
```

---

## Ordnerstruktur für Dokumente

Lege deine PDF-Dateien in der folgenden Struktur ab:

```
documents/
├── document1/
│   └── beispiel.pdf
├── document2/
│   └── beispiel.pdf
├── document3/
│   └── beispiel.pdf
├── document4/
│   └── beispiel.pdf
└── document5/
    └── beispiel.pdf
```

> **Hinweis:** Pro Ordner wird jeweils die erste gefundene `.pdf`-Datei verwendet.

---

## Nutzung

```bash
python main.py
```

Das System führt automatisch alle Tests durch und speichert die Ergebnisse als Excel-Dateien:
- `Auswertung_Doc1.xlsx` bis `Auswertung_Doc5.xlsx`
- `Auswertung_Gesamt.xlsx`

---

## Drei kritische Schutzmechanismen

### 1. HuggingFace Symlink-Fix

In `main.py` werden **vor allen anderen Imports** die folgenden Umgebungsvariablen gesetzt:

```python
import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "0"
```

Dies verhindert Fehler und Warnungen auf Firmen-Laptops mit eingeschränkten Berechtigungen (keine Symlinks) und restriktiven Firewalls.

### 2. Docling RAM-Schutz

In `src/toolset.py` wird der `DocumentConverter` mit RAM-schonenden Optionen initialisiert:

```python
pipeline_options = PdfPipelineOptions(
    do_ocr=False,
    generate_page_images=False,
)
```

OCR und Seitenbilder verbrauchen enorm viel RAM. Durch deren Deaktivierung bleibt das System auf Laptops mit begrenztem Arbeitsspeicher lauffähig.

### 3. Harte Timeouts für LLM-Aufrufe

Alle Azure OpenAI API-Calls in `src/agent.py` laufen über `_call_llm()`, das einen `httpx.Timeout` verwendet:

```python
self._client = AzureOpenAI(
    ...
    timeout=httpx.Timeout(float(config.llm_timeout)),
)
```

Dies verhindert unendliches Hängenbleiben bei Netzwerkproblemen oder langsamen API-Antworten.

---

## Anpassung der Testfragen

Die Testfragen in `tester.py` sind generisch formuliert und können einfach angepasst werden:

```python
TEST_QUESTIONS = {
    1: [
        "Meine spezifische Frage für Dokument 1?",
        ...
    ],
    ...
}
```

---

## Beispielausgabe

```
============================================================
📄 Dokument 1: bericht.pdf
============================================================
🔨 Generiere Index...
✅ Index erstellt (3842 Zeichen)

--- Frage 1/10 ---
❓ Frage: Was ist das Hauptthema des Dokuments?
✅ Antwort: Das Dokument behandelt die Optimierung von Lieferketten...
⏱️  Dauer: 4.21s
🔢 Tokens: 1243 (Prompt: 987, Completion: 256)
📚 Quellen: Einleitung, Kapitel 2 - Methodik
🔄 Iterationen: 1

============================================================
📊 Zusammenfassung Dokument 1
============================================================
   Durchschn. Dauer: 5.32s
   Gesamt-Tokens: 14521
   Gefundene Antworten: 9/10
💾 Ergebnisse gespeichert: Auswertung_Doc1.xlsx
```

---

## Troubleshooting

| Problem | Lösung |
|---|---|
| `AZURE_OPENAI_ENDPOINT ist nicht gesetzt` | `.env`-Datei erstellen und befüllen (siehe `.env.example`) |
| `Docling konnte nicht initialisiert werden` | `pip install docling>=2.0.0` prüfen |
| `LLM-Timeout nach 30s` | `LLM_TIMEOUT` in `.env` erhöhen (z.B. auf `60`) |
| `Keine PDF in documents/document1 gefunden` | Ordnerstruktur prüfen (siehe oben) |
| `ModuleNotFoundError` | `pip install -r requirements.txt` erneut ausführen |
| `OutOfMemoryError` bei Docling | OCR ist bereits deaktiviert; weitere PDFs schließen |

---

## Projektstruktur

```
src/
├── __init__.py
├── config.py          # Zentrale Konfiguration + Environment-Variablen
├── toolset.py         # PDFReader mit Docling + Caching
└── agent.py           # RAG-Agent mit Azure OpenAI
tester.py              # Test-Orchestrator für 5 PDFs × 10 Fragen
main.py                # Einstiegspunkt mit HF Symlink-Fix
requirements.txt       # Alle Dependencies
.env.example           # Template für Azure OpenAI Credentials
README.md              # Diese Dokumentation
```