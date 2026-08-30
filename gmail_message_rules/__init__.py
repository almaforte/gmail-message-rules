"""
gmail_message_rules

Regole obbligatorie di formattazione per qualunque email inviata da un
progetto di Alberto, indipendentemente dalla casella mittente o dal
repository che la invia. Nate dentro gmail-read-send-mcp (il connettore
per am.forte@almaval.ch, info@corsalis.ch, endolift@corsalis.ch,
forte.albertomaria@gmail.com) ed estratte qui il 30.08.2026 perche' vanno
applicate ovunque, non riscritte in ogni repository.

Le regole imposte, in ordine di applicazione da build_message():

1. html_body e' obbligatorio: niente messaggi in solo testo semplice.
2. Niente trattini lunghi (em dash "-", en dash "-", trattino
   orizzontale) in oggetto, corpo o html_body: sostituiti in automatico
   con un trattino corto "-".
3. Niente firma o formula di chiusura scritta a mano quando viene passata
   una firma ufficiale (signature_text/signature_html): una chiusura
   scritta a mano viene individuata e tolta prima di appendere la firma
   vera, per evitare un doppione.
4. Una sola riga vuota tra i paragrafi del corpo, e tra il corpo e la
   firma: qualunque tag di blocco (<p>, <div>, <ul>, <ol>, <table>,
   titoli, <blockquote>) porta gia' il proprio margine verticale in
   Gmail, quindi un <br> messo subito prima o dopo un tag di blocco e'
   ridondante e produce una riga vuota in piu'.

Ogni regola e' anche esposta come funzione a se stante, per chi vuole
applicarle singolarmente invece di passare da build_message().

Vedi CONVENTIONS.md in questo repository per la storia di ciascuna
regola: perche' esiste, quali bug ha risolto, quali limiti ha.
"""

from .rules import (
    HtmlBodyRequiredError,
    build_message,
    strip_long_dashes,
    strip_manual_closing,
    ends_with_block_tag,
    normalize_paragraph_spacing,
    wrap_html,
    apply_style,
    DEFAULT_STYLE,
    DEFAULT_CLOSING_PHRASES,
)

__all__ = [
    "HtmlBodyRequiredError",
    "build_message",
    "strip_long_dashes",
    "strip_manual_closing",
    "ends_with_block_tag",
    "normalize_paragraph_spacing",
    "wrap_html",
    "apply_style",
    "DEFAULT_STYLE",
    "DEFAULT_CLOSING_PHRASES",
]

__version__ = "1.0.0"
