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


def test_build_message_strips_dashes_everywhere():
    result = build_message(
        subject="Test — con trattino",
        body="Corpo — con trattino – e un altro ―.",
        html_body="<p>Corpo — con trattino.</p>",
    )
    assert "—" not in result["subject"]
    assert "–" not in result["subject"]
    assert "—" not in result["html_body"]
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
