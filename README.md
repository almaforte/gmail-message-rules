# gmail-message-rules

Regole obbligatorie di formattazione per qualunque email inviata dai
progetti di Alberto, da qualunque casella. Nate dentro
[gmail-read-send-mcp](https://github.com/almaforte/gmail-read-send-mcp)
ed estratte qui il 30.08.2026 perche' vanno applicate in ogni
repository che invia email, non riscritte ogni volta.

Vedi [CONVENTIONS.md](./CONVENTIONS.md) per il perche' di ciascuna
regola: quali bug ha risolto, quali limiti ha, come e' stata verificata.

## Le regole

1. **`html_body` sempre obbligatorio.** Nessun messaggio in solo testo
   semplice: se manca, `build_message` solleva `HtmlBodyRequiredError`
   prima di costruire qualsiasi cosa.
2. **Niente trattini lunghi, mai.** Em dash (—), en dash (–) e trattino
   orizzontale (―) vengono sostituiti in automatico con un trattino
   corto "-", in oggetto, corpo e `html_body`.
3. **Niente firma o chiusura scritta a mano se ne viene passata una
   ufficiale.** Una chiusura tipo "Cordialement, Alberto" scritta a mano
   verso la fine del messaggio viene individuata e tolta prima di
   appendere la firma vera, per evitare un doppione.
4. **Una sola riga vuota ovunque**, tra i paragrafi del corpo e tra il
   corpo e la firma: nessun `<br>` ridondante subito prima o dopo un tag
   di blocco che Gmail spazia gia' da solo.

## Installazione

Sempre dall'ultima versione di `main` (nessun tag pinnato: un
aggiornamento a queste regole si applica a tutti i repository collegati
al prossimo deploy):

```
pip install git+https://github.com/almaforte/gmail-message-rules.git
```

Oppure, in `requirements.txt`:

```
git+https://github.com/almaforte/gmail-message-rules.git
```

## Uso diretto delle regole

```python
from gmail_message_rules import build_message, HtmlBodyRequiredError

try:
    result = build_message(
        subject="Oggetto del messaggio",
        body="Testo semplice del corpo...",
        html_body="<p>Corpo in HTML...</p>",
        signature_text="Cordialement,\n\nNome Cognome",   # opzionale
        signature_html="Cordialement,<br><br>Nome Cognome", # opzionale
    )
except HtmlBodyRequiredError as exc:
    ...  # html_body mancante

# result = {"subject": ..., "text_body": ..., "html_body": ...}
# pronto per essere messo in un MIMEText multipart/alternative
```

Ogni regola e' anche disponibile singolarmente, per chi vuole applicarle
una alla volta invece di passare da `build_message`:
`strip_long_dashes`, `strip_manual_closing`, `ends_with_block_tag`,
`normalize_paragraph_spacing`, `wrap_html`, `apply_style`.

## Nuovo connettore MCP da zero

La cartella [`template/`](./template) contiene uno scheletro completo di
connettore MCP (OAuth Google, pagina `/setup`, tool `send_email` /
`create_draft` / `reply_email`), gia' collegato a `build_message`. Per
un nuovo repository:

1. Copia `template/server.py` e `template/config_example.py` nel nuovo
   repository.
2. Rinomina `config_example.py` in `config.py` e personalizzalo: le tue
   caselle, le tue firme (vedi i commenti nel file).
3. Aggiungi `git+https://github.com/almaforte/gmail-message-rules.git`
   e le dipendenze di [`requirements.txt`](./requirements.txt) al
   `requirements.txt` del nuovo repository.
4. Imposta le variabili d'ambiente elencate in cima a `server.py`
   (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SERVER_URL`,
   `ADMIN_PASSWORD`, `FERNET_KEY`, `TOKENS_FILE`).
5. Estendi `server.py` con eventuali tool specifici del nuovo progetto
   (allegati, filtri, liste), lasciando `send_email` / `create_draft` /
   `reply_email` cosi' come sono: sono il punto in cui le regole di
   questo pacchetto vengono applicate.

Non copiare o riscrivere la logica di `strip_long_dashes`,
`strip_manual_closing`, `normalize_paragraph_spacing` o simili in un
nuovo repository: se manca qualcosa, va aggiunto qui, cosi' vale subito
per tutti i progetti collegati.

## Test

```
pip install -r requirements.txt
python -m pytest tests/
```

## Aggiornare le regole

Quando cambia una regola (una nuova formula di chiusura da riconoscere,
un nuovo caso di spaziatura ridondante, eccetera):

1. Modifica `gmail_message_rules/rules.py`.
2. Aggiungi o aggiorna un test in `tests/test_rules.py` che dimostri il
   comportamento corretto, prima di aprire una pull request.
3. Aggiorna `CONVENTIONS.md` con il razionale del cambiamento e la data.
4. Fai il commit su `main`. Ogni repository che installa da `main` (non
   da un tag) applichera' il cambiamento al prossimo deploy, senza
   bisogno di toccare quel repository.
