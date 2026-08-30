"""
gmail_message_rules.rules

Implementazione delle regole. Nessuna dipendenza da un account, una
casella o un provider OAuth specifico: tutto quello che serve viene
passato come parametro da chi chiama. Il connettore MCP di ogni
repository resta responsabile di OAuth, invio via API e delle proprie
firme; questo modulo si occupa solo di costruire un html_body e un
corpo testuale corretti secondo le regole.
"""

import re
from typing import Optional

from bs4 import BeautifulSoup, NavigableString


# ---------------------------------------------------------------------------
# html_body obbligatorio
# ---------------------------------------------------------------------------


class HtmlBodyRequiredError(ValueError):
    """
    Sollevato quando manca html_body. Un messaggio in solo testo semplice
    e' sempre un incidente, mai una scelta deliberata: l'errore deve
    arrivare al momento della chiamata, non produrre silenziosamente una
    mail poco curata (vedi Alberto, 30.08.2026).
    """


def _require_html_body(html_body: str) -> None:
    if not html_body:
        raise HtmlBodyRequiredError(
            "html_body e' obbligatorio: fornisci il corpo del messaggio in HTML "
            "(paragrafi <p>, eventuali <strong>/<ol>/<ul>), non solo in testo semplice."
        )


# ---------------------------------------------------------------------------
# Niente trattini lunghi, mai
# ---------------------------------------------------------------------------

_LONG_DASH_CHARS = "—–―"  # em dash, en dash, trattino orizzontale
_LONG_DASH_PATTERN = re.compile(f"[{_LONG_DASH_CHARS}]")


def strip_long_dashes(text: str) -> str:
    """
    Sostituisce ogni trattino lungo con un trattino corto "-". Non tocca
    nient'altro: non normalizza spazi, non tocca altri segni di
    punteggiatura, non tocca lettere accentate. Si applica a oggetto,
    corpo testuale e html_body, perche' un trattino lungo puo' comparire
    ovunque in un testo scritto di getto.
    """
    if not text:
        return text
    return _LONG_DASH_PATTERN.sub("-", text)


# ---------------------------------------------------------------------------
# Niente firma o formula di chiusura scritta a mano
# ---------------------------------------------------------------------------

DEFAULT_CLOSING_PHRASES = [
    "bien cordialement",
    "cordialement",
    "bests",
    "best regards",
    "kind regards",
    "regards",
    "cordiali saluti",
    "distinti saluti",
    "un cordiale saluto",
]


def _closing_pattern_text(phrases: list) -> re.Pattern:
    return re.compile(
        r"(?im)^\s*(" + "|".join(re.escape(p) for p in phrases) + r")\s*[,.:]?\s*\n.*\Z",
        re.DOTALL,
    )


def _closing_pattern_html(phrases: list) -> re.Pattern:
    return re.compile(
        r"(?is)<(p|div)[^>]*>\s*(" + "|".join(re.escape(p) for p in phrases) + r")\s*[,.:]?\s*(<br\s*/?>)?\s*</\1>",
    )


def strip_manual_closing(
    body: str,
    html_body: str,
    closing_phrases: Optional[list] = None,
) -> tuple:
    """
    Toglie una formula di chiusura scritta a mano ("Cordialement, ...",
    "Bests, ...") e tutto cio' che la segue, sia dal testo semplice sia
    dall'HTML, cosi' non finisce doppiata con la firma ufficiale che
    verra' appesa dopo. Da chiamare solo quando una firma verra' davvero
    aggiunta: su un messaggio senza firma non c'e' rischio di doppione.

    L'euristica taglia solo se la formula compare nell'ultimo quarto del
    testo, per non tagliare per errore un paragrafo che la cita a meta'
    messaggio per altri motivi. closing_phrases e' sostituibile per chi
    usa formule diverse dalle predefinite (francese/italiano/inglese).
    """
    phrases = closing_phrases if closing_phrases is not None else DEFAULT_CLOSING_PHRASES

    new_body = body
    if body:
        match = _closing_pattern_text(phrases).search(body)
        if match and match.start() >= len(body) * 0.75:
            new_body = body[: match.start()].rstrip()

    new_html_body = html_body
    if html_body:
        match = _closing_pattern_html(phrases).search(html_body)
        if match and match.start() >= len(html_body) * 0.75:
            new_html_body = html_body[: match.start()].rstrip()

    return new_body, new_html_body


# ---------------------------------------------------------------------------
# Una sola riga vuota ovunque: tra i paragrafi, e tra il corpo e la firma
# ---------------------------------------------------------------------------

# Tag di blocco che Gmail spazia gia' da soli con un margine verticale di
# default. Un <br> messo a mano subito prima o subito dopo uno di questi
# tag si somma a quel margine e produce una riga vuota in piu'.
BLOCK_SPACING_TAGS = {
    "p", "div", "ul", "ol", "table", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6",
}


def ends_with_block_tag(fragment: str) -> bool:
    """
    True se l'ultimo nodo di primo livello del frammento (spazi bianchi a
    parte) e' uno dei tag in BLOCK_SPACING_TAGS. Serve a decidere se un
    <br> di separazione verso cio' che segue e' ridondante: un </p> porta
    gia' il proprio margine inferiore, quindi un <br> subito dopo produce
    comunque una riga vuota in piu', anche se dall'altra parte del <br>
    c'e' testo semplice invece di un altro tag di blocco (il caso tipico
    di una firma HTML che comincia con "Cordialement," in chiaro).
    """
    if not fragment:
        return False
    soup = BeautifulSoup(fragment, "html.parser")
    nodes = list(soup.contents)
    while nodes and isinstance(nodes[-1], NavigableString) and not nodes[-1].strip():
        nodes.pop()
    if not nodes:
        return False
    return getattr(nodes[-1], "name", None) in BLOCK_SPACING_TAGS


def normalize_paragraph_spacing(fragment: str) -> str:
    """
    Toglie ogni sequenza di <br> (con eventuali spazi bianchi attorno) che
    si trova direttamente tra due tag di blocco di primo livello nel
    frammento. Non tocca un <br> che sta tra testo semplice e un tag di
    blocco, ne' un <br> dentro testo non strutturato: solo la spaziatura
    ridondante tra blocchi che Gmail spazia gia' da soli.
    """
    if not fragment:
        return fragment
    soup = BeautifulSoup(fragment, "html.parser")
    nodes = list(soup.contents)
    i = 0
    while i < len(nodes):
        node = nodes[i]
        if getattr(node, "name", None) == "br":
            prev_idx = i - 1
            while prev_idx >= 0 and isinstance(nodes[prev_idx], NavigableString) and not nodes[prev_idx].strip():
                prev_idx -= 1
            j = i
            while j < len(nodes) and (
                getattr(nodes[j], "name", None) == "br"
                or (isinstance(nodes[j], NavigableString) and not nodes[j].strip())
            ):
                j += 1
            prev_is_block = prev_idx >= 0 and getattr(nodes[prev_idx], "name", None) in BLOCK_SPACING_TAGS
            next_is_block = j < len(nodes) and getattr(nodes[j], "name", None) in BLOCK_SPACING_TAGS
            if prev_is_block and next_is_block:
                for k in range(i, j):
                    nodes[k].extract()
                nodes = list(soup.contents)
                continue
            i = j
            continue
        i += 1
    return str(soup)


# ---------------------------------------------------------------------------
# Stile HTML imposto tag per tag
# ---------------------------------------------------------------------------

DEFAULT_STYLE = {
    "font_family": "Verdana, Geneva, sans-serif",
    "font_size": "10px",
    "color": "#666666",
}

# Tag ai quali lo stile viene imposto uno per uno. Le immagini sono escluse
# di proposito. I link ricevono carattere e dimensione ma non il colore,
# cosi' restano blu e riconoscibili come link.
STYLED_TAGS = [
    "p", "div", "span", "li", "ul", "ol",
    "table", "thead", "tbody", "tr", "td", "th",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "b", "strong", "em", "i", "u", "small", "pre", "code",
]


def _style_attr(style: dict) -> str:
    return (
        f"font-family:{style['font_family']};"
        f"font-size:{style['font_size']};"
        f"color:{style['color']};"
    )


def _link_attr(style: dict) -> str:
    return (
        f"font-family:{style['font_family']};"
        f"font-size:{style['font_size']};"
    )


def apply_style(fragment: str, style: Optional[dict] = None) -> str:
    """
    Impone lo stile a ogni tag di blocco del frammento HTML. Lo stile
    viene messo PRIMA di un eventuale stile gia' presente sul tag: in CSS
    in linea vince l'ultima dichiarazione, quindi un'eccezione scritta a
    mano nel messaggio resta prioritaria. L'applicazione tag per tag e'
    necessaria perche' Gmail trasmette il carattere di un div contenitore
    ai paragrafi ma lo perde sugli elenchi puntati e lo ignora nelle
    celle di tabella.
    """
    if not fragment:
        return fragment
    style = style or DEFAULT_STYLE
    soup = BeautifulSoup(fragment, "html.parser")
    attr = _style_attr(style)
    for tag in soup.find_all(STYLED_TAGS):
        existing = tag.get("style", "")
        tag["style"] = attr + existing
    link_attr = _link_attr(style)
    for tag in soup.find_all("a"):
        existing = tag.get("style", "")
        tag["style"] = link_attr + existing
    return str(soup)


def wrap_html(inner_html: str, style: Optional[dict] = None) -> str:
    """
    Normalizza la spaziatura tra paragrafi e applica lo stile, poi avvolge
    tutto in un div contenitore con lo stesso stile (per i frammenti di
    testo nudo che non hanno un tag proprio).
    """
    style = style or DEFAULT_STYLE
    normalized = normalize_paragraph_spacing(inner_html)
    return f'<div style="{_style_attr(style)}">{apply_style(normalized, style)}</div>'


# ---------------------------------------------------------------------------
# Punto di ingresso unico: applica tutte le regole in ordine
# ---------------------------------------------------------------------------


def build_message(
    subject: str,
    body: str,
    html_body: str,
    signature_text: str = "",
    signature_html: str = "",
    closing_phrases: Optional[list] = None,
    style: Optional[dict] = None,
) -> dict:
    """
    Applica tutte le regole in ordine e restituisce un dict pronto per
    costruire il messaggio MIME:

        {"subject": ..., "text_body": ..., "html_body": ...}

    dove html_body e' gia' avvolto nel div di stile e comprensivo di
    firma (se signature_html e' stato passato), e text_body e' il corpo
    testuale con la firma testuale in coda (se signature_text e' stato
    passato).

    Solleva HtmlBodyRequiredError se html_body e' vuoto.

    Chi chiama resta responsabile di: costruire il MIME vero e proprio,
    allegare eventuali immagini inline, e inviarlo tramite l'API scelta.
    Questa funzione non tocca destinatari, header o invio.
    """
    _require_html_body(html_body)

    subject = strip_long_dashes(subject)
    body = strip_long_dashes(body)
    html_body = strip_long_dashes(html_body)

    if signature_text or signature_html:
        body, html_body = strip_manual_closing(body, html_body, closing_phrases=closing_phrases)

    text_body = body
    if signature_text:
        text_body = f"{body}\n{signature_text}"

    inner_html = html_body
    if signature_html:
        separator = "" if ends_with_block_tag(html_body) else "<br>"
        inner_html = f"{html_body}{separator}{signature_html}"

    wrapped_html = wrap_html(inner_html, style=style)

    return {
        "subject": subject,
        "text_body": text_body,
        "html_body": wrapped_html,
    }
