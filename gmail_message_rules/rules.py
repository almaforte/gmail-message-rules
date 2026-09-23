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
# Un em dash, un en dash, un trattino orizzontale, oppure due o piu' trattini
# corti ASCII consecutivi (surrogato manuale dell'em dash: "--", "---", ...):
# in tutti questi casi il risultato voluto e' un unico trattino corto "-".
_LONG_DASH_PATTERN = re.compile(f"[{_LONG_DASH_CHARS}]+|-{{2,}}")


def strip_long_dashes(text: str) -> str:
    """
    Sostituisce ogni trattino lungo, o sequenza di due o piu' trattini
    corti ASCII scritti di seguito ("--", "---", ...), con un unico
    trattino corto "-". Un trattino corto isolato non viene mai toccato.
    Non tocca nient'altro: non normalizza spazi, non tocca altri segni di
    punteggiatura, non tocca lettere accentate. Si applica a oggetto,
    corpo testuale e html_body, perche' un trattino lungo (o il suo
    surrogato "--" digitato a mano) puo' comparire ovunque in un testo
    scritto di getto.
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


def _closing_first_line_pattern(phrases: list) -> re.Pattern:
    """
    Riconosce una formula di chiusura quando e' la PRIMA riga di testo di
    un blocco HTML, seguita o no da altre righe nello stesso blocco (il
    caso reale di una firma manuale: "Cordialement,<br>Alberto",
    "Bien cordialement,<br><br>Dr Forte<br>Almaval"). A differenza di un
    pattern che richiede la chiusura come UNICO contenuto del blocco,
    questo riconosce anche una chiusura seguita da altre righe nello
    stesso tag, che e' il caso piu' comune in pratica (vedi
    CONVENTIONS.md, correzione del 30.08.2026).
    """
    return re.compile(
        r"(?i)^\s*(" + "|".join(re.escape(p) for p in phrases) + r")\s*[,.:]?\s*$"
    )


def _strip_manual_closing_html(html_body: str, phrases: list) -> str:
    """
    Cerca, tra i tag di blocco di primo livello di html_body, il primo la
    cui prima riga di testo e' una formula di chiusura nota, purche' quel
    blocco si trovi nell'ultimo quarto del documento (stessa soglia usata
    per il testo semplice, per non tagliare per errore una chiusura citata
    a meta' messaggio per altri motivi). Se lo trova, rimuove quel blocco
    e tutto cio' che lo segue.

    A differenza della versione precedente (che richiedeva la formula come
    UNICO contenuto testuale di un <p>/<div> isolato), questa riconosce
    anche una firma manuale su piu' righe nello stesso blocco, il caso di
    gran lunga piu' frequente in pratica (vedi CONVENTIONS.md, correzione
    del 30.08.2026).
    """
    if not html_body:
        return html_body
    soup = BeautifulSoup(html_body, "html.parser")
    top_nodes = list(soup.contents)
    pattern = _closing_first_line_pattern(phrases)
    serialized = [str(node) for node in top_nodes]
    total_len = sum(len(s) for s in serialized)

    running = 0
    cut_from_idx = None
    for i, node in enumerate(top_nodes):
        if getattr(node, "name", None):
            text = node.get_text(separator="\n").strip()
            first_line = text.split("\n")[0].strip() if text else ""
            if first_line and pattern.match(first_line) and running >= total_len * 0.75:
                cut_from_idx = i
                break
        running += len(serialized[i])

    if cut_from_idx is None:
        return html_body

    trimmed = BeautifulSoup("", "html.parser")
    for node in top_nodes[:cut_from_idx]:
        trimmed.append(node)
    return str(trimmed).rstrip()


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

    Lato HTML, la chiusura viene riconosciuta quando e' la prima riga di
    testo di un blocco di primo livello (non solo quando e' l'unico
    contenuto del blocco): una firma manuale scritta su piu' righe nello
    stesso tag, per esempio "<p>Cordialement,<br>Alberto</p>", viene
    quindi riconosciuta e tolta per intero, insieme a tutto cio' che la
    segue (vedi CONVENTIONS.md, correzione del 30.08.2026).
    """
    phrases = closing_phrases if closing_phrases is not None else DEFAULT_CLOSING_PHRASES

    new_body = body
    if body:
        match = _closing_pattern_text(phrases).search(body)
        if match and match.start() >= len(body) * 0.75:
            new_body = body[: match.start()].rstrip()

    new_html_body = _strip_manual_closing_html(html_body, phrases) if html_body else html_body

    return new_body, new_html_body


# ---------------------------------------------------------------------------
# Grassetto riservato ai titoli o a poche parole determinanti, mai alla prosa
# ---------------------------------------------------------------------------

# Oltre questo numero di parole, un <strong>/<b> SPARSO NELLA PROSA smette di
# essere "una data, un nome proprio, una parola chiave" e diventa un pezzo di
# prosa intero messo in grassetto: la regola di Alberto (30.08.2026, memoria
# di progetto) lo vieta nel corpo corrente di un messaggio. Il limite e'
# volutamente largo (una data lunga o un intitule breve ci stanno comunque
# dentro) per non toccare mai un uso legittimo.
MAX_BOLD_WORDS = 6

# Tetto applicato invece agli INTERTITOLI, cioe' ai <strong>/<b> che
# costituiscono da soli tutto il contenuto del loro blocco. Un titolo di
# blocco puo' essere piu' lungo di sei parole senza smettere di essere un
# titolo, ma oltre questo tetto non e' piu' un titolo: e' un paragrafo
# messo in evidenza, e il grassetto se ne va come per la prosa.
MAX_HEADING_WORDS = 20

# Blocchi il cui contenuto, se e' interamente un <strong>/<b>, va letto come
# un intertitolo e non come prosa in grassetto.
_HEADING_PARENT_TAGS = {"p", "div", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"}

# Punteggiatura che chiude una frase. Un intertitolo non la porta mai; una
# frase di prosa si'. I due punti NON sono in questa lista: un intertitolo
# puo' legittimamente finire con ":".
_SENTENCE_END = ".!?…"


def _is_block_heading(tag, max_heading_words: int) -> bool:
    """
    True se questo <strong>/<b> e' un intertitolo, cioe' un titolo di
    blocco, e non del grassetto sparso nella prosa.

    Tre condizioni insieme, e servono tutte e tre:

    1. Il tag costituisce da solo TUTTO il contenuto testuale del suo
       blocco. "<p><strong>Titre</strong></p>" e' un titolo;
       "<p>Le <strong>14 septembre</strong> a 9h.</p>" e' prosa con una
       data in evidenza.
    2. Il testo non finisce con una punteggiatura di frase. Un
       intertitolo non porta punto finale, una frase di prosa si'. E' il
       criterio che distingue "Ce qui reste vrai, et qui explique votre
       question" da "Ceci est une phrase entiere mise en gras sans aucune
       raison valable ici."
    3. Il testo resta sotto max_heading_words parole. Oltre, per quanto
       privo di punto, non e' piu' un titolo.
    """
    parent = tag.parent
    if parent is None or getattr(parent, "name", None) not in _HEADING_PARENT_TAGS:
        return False

    text = tag.get_text().strip()
    if not text:
        return False

    if parent.get_text().strip() != text:
        return False

    if text[-1] in _SENTENCE_END:
        return False

    return len(text.split()) <= max_heading_words


def limit_bold(
    fragment: str,
    max_words: int = MAX_BOLD_WORDS,
    max_heading_words: int = MAX_HEADING_WORDS,
) -> str:
    """
    Rimuove un <strong> o <b> che racchiude piu' di max_words parole DI
    PROSA: il tag viene tolto, il testo resta al suo posto ma senza piu'
    grassetto. Un <strong> corto (una data, un nome proprio, un intitule
    di poche parole) non viene mai toccato.

    NON tocca mai:

    - un <strong>/<b> dentro un titolo <h1>-<h6>: un titolo puo'
      legittimamente essere interamente in evidenza;
    - un INTERTITOLO, cioe' un <strong>/<b> che costituisce da solo tutto
      il contenuto del suo blocco, non finisce con un punto e resta sotto
      max_heading_words parole (vedi _is_block_heading).

    IL BUG CHE QUESTA SECONDA ECCEZIONE CORREGGE, 23.09.2026. Prima, un
    intertitolo di sette parole perdeva il grassetto mentre uno di tre lo
    teneva, nello stesso messaggio. Il lettore vedeva allora una gerarchia
    inesistente e cercava la differenza di livello che quel grassetto
    mancante sembrava segnalare. Il difetto non si vedeva scrivendo, solo
    leggendo il messaggio ricevuto, e per settimane e' stato attribuito a
    chi scriveva invece che a questa regola.

    Si applica dopo normalize_paragraph_spacing e prima di apply_style,
    per non dover rianalizzare uno stile gia' posato.
    """
    if not fragment:
        return fragment
    soup = BeautifulSoup(fragment, "html.parser")
    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
    for tag in soup.find_all(["strong", "b"]):
        if tag.find_parent(heading_tags):
            continue
        if _is_block_heading(tag, max_heading_words):
            continue
        word_count = len(tag.get_text().split())
        if word_count > max_words:
            tag.unwrap()
    return str(soup)


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


def _style_attr_without_color(style: dict) -> str:
    return (
        f"font-family:{style['font_family']};"
        f"font-size:{style['font_size']};"
    )


def _link_attr(style: dict) -> str:
    return (
        f"font-family:{style['font_family']};"
        f"font-size:{style['font_size']};"
    )


def _has_declared_color_above(tag) -> bool:
    """
    True se un antenato di questo tag dichiara gia' un colore, con
    <font color="..."> oppure con uno style che contiene "color:".

    Serve a non schiacciare una scelta di colore fatta apposta in un
    messaggio o in una firma. Vedi apply_style per il caso reale.
    """
    for ancestor in tag.parents:
        if getattr(ancestor, "name", None) is None:
            continue
        if ancestor.name == "font" and ancestor.get("color"):
            return True
        if "color:" in (ancestor.get("style") or ""):
            return True
    return False


def apply_style(fragment: str, style: Optional[dict] = None) -> str:
    """
    Impone lo stile a ogni tag di blocco del frammento HTML. Lo stile
    viene messo PRIMA di un eventuale stile gia' presente sul tag: in CSS
    in linea vince l'ultima dichiarazione, quindi un'eccezione scritta a
    mano nel messaggio resta prioritaria. L'applicazione tag per tag e'
    necessaria perche' Gmail trasmette il carattere di un div contenitore
    ai paragrafi ma lo perde sugli elenchi puntati e lo ignora nelle
    celle di tabella.

    UN TAG SOTTO UN COLORE GIA' DICHIARATO riceve carattere e dimensione
    ma NON il colore. Il caso reale, 23.09.2026: il disclaimer in calce
    alla firma di gestion@almaval.ch e' scritto in grigio chiaro con
    <font color="#999999">, e usciva invece dello stesso grigio del
    corpo. Il motivo e' che il colore veniva imposto anche al <i>
    annidato dentro quel <font>, e uno stile in linea sul figlio batte
    l'attributo color del padre. Chi sceglie un grigio piu' chiaro per
    una nota a pie' di firma se lo tiene.

    L'insieme dei tag da risparmiare si calcola su TUTTO il frammento
    prima di toccare qualunque cosa. Senza questa precauzione il primo
    tag, ricevendo il colore, renderebbe protetti tutti i suoi
    discendenti, e l'applicazione tag per tag smetterebbe di funzionare
    proprio dove serve, cioe' negli elenchi e nelle celle.
    """
    if not fragment:
        return fragment
    style = style or DEFAULT_STYLE
    soup = BeautifulSoup(fragment, "html.parser")

    styled_tags = soup.find_all(STYLED_TAGS)
    protected = {id(tag) for tag in styled_tags if _has_declared_color_above(tag)}

    attr = _style_attr(style)
    attr_without_color = _style_attr_without_color(style)
    for tag in styled_tags:
        existing = tag.get("style", "")
        chosen = attr_without_color if id(tag) in protected else attr
        tag["style"] = chosen + existing

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
    max_bold_words: int = MAX_BOLD_WORDS,
    max_heading_words: int = MAX_HEADING_WORDS,
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

    html_body = limit_bold(
        html_body,
        max_words=max_bold_words,
        max_heading_words=max_heading_words,
    )

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
