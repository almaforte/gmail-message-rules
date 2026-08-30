"""
Test delle regole di gmail_message_rules. Verificano la struttura
dell'HTML/testo prodotto, non come Gmail lo mostra davvero: restano
comunque il primo controllo da fare prima di ogni cambiamento (vedi
CONVENTIONS.md sul perche' un fix di resa visiva va comunque confermato
guardando una bozza vera).
"""

import pytest

from gmail_message_rules import build_message, HtmlBodyRequiredError
from gmail_message_rules.rules import (
    strip_long_dashes,
    strip_manual_closing,
    limit_bold,
    ends_with_block_tag,
    normalize_paragraph_spacing,
)


def test_html_body_required():
    with pytest.raises(HtmlBodyRequiredError):
        build_message(subject="Oggetto", body="corpo", html_body="")


def test_strip_long_dashes_all_variants():
    assert strip_long_dashes("a — b") == "a - b"
    assert strip_long_dashes("a – b") == "a - b"
    assert strip_long_dashes("a ― b") == "a - b"
    assert strip_long_dashes("gia' un trattino corto - qui") == "gia' un trattino corto - qui"
    assert strip_long_dashes("") == ""
    assert strip_long_dashes(None) is None


def test_strip_long_dashes_does_not_touch_accents():
    text = "Voici un message avec des accents : é, è, à, ç, médical."
    assert strip_long_dashes(text) == text


def test_strip_long_dashes_collapses_double_short_dash():
    # Il trattino doppio ASCII "--" e' il surrogato manuale dell'em dash
    # (spesso digitato di getto): va ridotto a un trattino corto singolo,
    # non lasciato come doppione (vedi CONVENTIONS.md, 30.08.2026).
    assert strip_long_dashes("a -- b") == "a - b"
    assert strip_long_dashes("a --- b") == "a - b"
    assert strip_long_dashes("a - b") == "a - b"


def test_build_message_strips_dashes_everywhere():
    result = build_message(
        subject="Test — con trattino -- doppio",
        body="Corpo — con trattino – e un altro ―.",
        html_body="<p>Corpo — con trattino -- doppio.</p>",
    )
    assert "—" not in result["subject"]
    assert "–" not in result["subject"]
    assert "--" not in result["subject"]
    assert "—" not in result["html_body"]
    assert "--" not in result["html_body"]
    assert "-" in result["subject"]


def test_strip_manual_closing_removes_when_near_end():
    long_body = (
        "Bonjour,\n\n"
        "Voici un message de test suffisamment long pour que la formule de "
        "cloture se trouve bien dans le dernier quart du texte.\n\n"
        "Cordialement,\nAlberto"
    )
    new_body, _ = strip_manual_closing(long_body, "")
    assert "Cordialement" not in new_body


def test_strip_manual_closing_keeps_when_not_near_end():
    short_body = "Corpo del messaggio.\n\nCordialement,\nAlberto"
    new_body, _ = strip_manual_closing(short_body, "")
    # Su un testo breve la formula non e' nell'ultimo quarto: resta intatta.
    assert "Cordialement" in new_body


def test_build_message_removes_duplicate_signature():
    sig_text = "Cordialement,\n\nDr Test\ntest@example.com"
    sig_html = "Cordialement,<br><br>Dr Test<br>test@example.com"
    long_body_text = (
        "Bonjour,\n\n"
        "Voici un message de test suffisamment long pour que la formule de "
        "cloture se trouve bien dans le dernier quart du texte, avec du "
        "contexte supplementaire pour allonger le message.\n\n"
        "Cordialement,\nAlberto"
    )
    long_body_html = (
        "<p>Bonjour,</p>"
        "<p>Voici un message de test suffisamment long pour que la formule de "
        "cloture se trouve bien dans le dernier quart du texte, avec du "
        "contexte supplementaire pour allonger le message.</p>"
        "<p>Cordialement,</p>"
    )
    result = build_message(
        subject="Oggetto",
        body=long_body_text,
        html_body=long_body_html,
        signature_text=sig_text,
        signature_html=sig_html,
    )
    assert result["text_body"].count("Cordialement") == 1
    assert result["html_body"].count("Cordialement") == 1


def test_ends_with_block_tag():
    assert ends_with_block_tag("<p>Testo.</p>") is True
    assert ends_with_block_tag("<p>Testo.</p>   ") is True
    assert ends_with_block_tag("Testo semplice senza tag.") is False
    assert ends_with_block_tag("<p>Testo.</p>coda in chiaro") is False
    assert ends_with_block_tag("") is False


def test_no_redundant_br_after_block_tag_before_signature():
    result = build_message(
        subject="Oggetto",
        body="Corpo semplice.",
        html_body="<p>Corpo semplice.</p>",
        signature_text="Cordialement,\n\nDr Test",
        signature_html="Cordialement,<br><br>Dr Test",
    )
    # Nessun <br> incollato subito dopo il tag di blocco che chiude il corpo.
    assert "</p><br>" not in result["html_body"]
    assert "</p>Cordialement" in result["html_body"] or "</p>" in result["html_body"]


def test_normalize_paragraph_spacing_removes_redundant_br_between_blocks():
    fragment = "<p>Uno.</p><br><br><p>Due.</p>"
    normalized = normalize_paragraph_spacing(fragment)
    assert "<br" not in normalized


def test_normalize_paragraph_spacing_keeps_br_in_plain_text():
    fragment = "Riga uno<br>Riga due, senza tag di blocco attorno."
    normalized = normalize_paragraph_spacing(fragment)
    assert "<br" in normalized


# --- Nuovi test per limit_bold (regola del 30.08.2026) ---


def test_limit_bold_keeps_short_bold():
    frag = "<p>Le <strong>14 septembre 2026</strong> a 9h.</p>"
    assert limit_bold(frag) == frag


def test_limit_bold_keeps_short_bold_with_b_tag():
    frag = "<p>Bonjour <b>Marie Dupont</b>,</p>"
    assert limit_bold(frag) == frag


def test_limit_bold_strips_long_bold_sentence():
    frag = "<p><strong>Ceci est une phrase entiere mise en gras sans aucune raison valable ici.</strong></p>"
    result = limit_bold(frag)
    assert "<strong>" not in result
    assert "Ceci est une phrase entiere" in result


def test_limit_bold_never_touches_headings():
    frag = "<h2><strong>Ceci est un titre de chapitre assez long avec plusieurs mots</strong></h2>"
    result = limit_bold(frag)
    assert "<strong>" in result


def test_limit_bold_empty_and_none():
    assert limit_bold("") == ""
    assert limit_bold(None) is None


def test_limit_bold_custom_max_words():
    frag = "<p><strong>Un deux trois quatre</strong></p>"
    assert "<strong>" in limit_bold(frag, max_words=6)
    assert "<strong>" not in limit_bold(frag, max_words=2)


def test_build_message_applies_limit_bold():
    html_body = (
        "<p><strong>Une phrase entiere en gras qui ne devrait jamais etre "
        "entierement mise en evidence comme ca.</strong></p>"
        "<p>Et une <strong>date importante</strong> ici.</p>"
    )
    result = build_message(subject="Oggetto", body="corpo", html_body=html_body)
    assert "Une phrase entiere en gras" in result["html_body"]
    assert "date importante</strong>" in result["html_body"]
