"""
config_example.py

Copia questo file in config.py (escluso da git, vedi .gitignore) e
personalizzalo per il tuo progetto: le tue caselle, le tue firme, e
un eventuale stile diverso da quello predefinito.

Ogni valore qui e' un esempio; server.py importa da config.py, non da
questo file.
"""

# ---------------------------------------------------------------------------
# Firme ufficiali per casella, in due versioni parallele:
#   SIGNATURES_TEXT  alimenta la parte testuale semplice / il fallback
#   SIGNATURES_HTML  alimenta la parte HTML, appesa dopo html_body
# Le due versioni vanno tenute sincronizzate a mano quando cambia una firma.
# Una casella assente da questi due dict non ha firma: i messaggi da
# quella casella escono senza chiusura automatica ne' controllo di
# doppione (vedi gmail_message_rules.strip_manual_closing).
# ---------------------------------------------------------------------------

SIGNATURES_TEXT = {
    "esempio@tuodominio.ch": (
        "Cordialement,\n\n"
        "Nome Cognome\n"
        "Ruolo\n\n"
        "esempio@tuodominio.ch\n"
        "+41 00 000 00 00\n"
        "tuodominio.ch"
    ),
}

SIGNATURES_HTML = {
    "esempio@tuodominio.ch": (
        "Cordialement,<br><br>"
        "Nome Cognome<br>"
        "Ruolo<br><br>"
        "esempio@tuodominio.ch<br>"
        "+41 00 000 00 00<br>"
        "tuodominio.ch"
    ),
}

# ---------------------------------------------------------------------------
# Stile imposto alla parte HTML dei messaggi. Lascia None per usare lo
# stile predefinito del pacchetto (gmail_message_rules.DEFAULT_STYLE:
# Verdana 10px #666666). Puoi anche differenziare per casella con
# STYLE_OVERRIDES, sul modello di SIGNATURES_TEXT/HTML.
# ---------------------------------------------------------------------------

STYLE = None  # oppure {"font_family": "...", "font_size": "...", "color": "..."}

STYLE_OVERRIDES: dict = {
    # "esempio@tuodominio.ch": {"color": "#444444"},
}

# ---------------------------------------------------------------------------
# Formule di chiusura da riconoscere ed eliminare se scritte a mano.
# Lascia None per usare l'elenco predefinito del pacchetto
# (francese/italiano/inglese, vedi gmail_message_rules.DEFAULT_CLOSING_PHRASES).
# ---------------------------------------------------------------------------

CLOSING_PHRASES = None
