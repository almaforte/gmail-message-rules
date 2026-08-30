# Perche' queste regole esistono

Questo repository nasce il 30.08.2026 come estrazione delle regole gia'
imposte nel codice di `gmail-read-send-mcp` (il connettore per
am.forte@almaval.ch, info@corsalis.ch, endolift@corsalis.ch,
forte.albertomaria@gmail.com), per poterle applicare a qualunque altro
repository di Alberto che invii email, da qualunque casella.

Prima di essere nel codice, le stesse regole vivevano solo come
preferenza salvata nella memoria di un assistente (non in un
repository). Si sono rivelate insufficienti: una preferenza va riletta
attivamente prima di ogni azione perche' faccia effetto, e in piu' di
un'occasione non lo e' stata, producendo lo stesso errore piu' volte di
seguito (un messaggio in testo semplice invece che HTML, una firma
duplicata, due righe vuote invece di una). Un vincolo nel codice non
dipende dal fatto che chi chiama lo strumento se ne ricordi: si applica
sempre, a ogni chiamata, da qualunque client MCP o script arrivi.

## Niente trattini lunghi, mai

Ne' nel testo dei messaggi (oggetto, corpo, firma), ne' nei titoli o nel
testo di questo repository (README, questo file, messaggi di commit).
Solo trattino corto normale "-", mai l'em dash o l'en dash. Se serve una
pausa o un inciso, si usa una virgola, due punti, o una frase separata.

Regola esplicita di Alberto (30.08.2026), dopo averla vista comparire nel
titolo di una bozza di prova. E' imposta a livello di codice da
`strip_long_dashes`, chiamata da `build_message` su `subject`, `body` e
`html_body` prima di qualunque altra elaborazione: ogni em dash (—), en
dash (–) o trattino orizzontale (―) viene sostituito con un trattino
corto "-" in automatico e in silenzio, senza bloccare la chiamata. Per il
testo di questo repository (README, questo file, messaggi di commit)
resta invece una regola di scrittura da rispettare a mano, perche' quel
testo non passa da `build_message`.

## html_body e' obbligatorio

Nessuno strumento costruito con questo pacchetto deve poter inviare o
mettere in bozza un messaggio in solo testo semplice: `build_message`
solleva `HtmlBodyRequiredError` se `html_body` e' vuoto, prima di
costruire qualsiasi cosa.

Motivo: un messaggio in testo semplice, su queste caselle, e' sempre un
incidente, mai una scelta deliberata. Rendere il campo opzionale lascia
la porta aperta a un client che se ne dimentica; renderlo obbligatorio
sposta l'errore al momento della chiamata, dove e' visibile e
correggibile subito, invece che nel messaggio gia' arrivato al
destinatario.

`html_body` deve essere HTML vero (paragrafi `<p>`, `<strong>` per
l'enfasi, `<ol>`/`<ul>` per gli elenchi), non testo semplice avvolto in un
unico tag. Lo stile (famiglia di carattere, dimensione, colore) e'
imposto dal pacchetto via `DEFAULT_STYLE` (sostituibile per progetto o
per casella): chi scrive il messaggio non deve indicarlo.

## Nessuna firma o formula di chiusura scritta a mano

Quando viene passata una firma (`signature_text`/`signature_html`), chi
scrive il messaggio non deve mai includere una formula di chiusura
("Cordialement, Alberto", "Bien cordialement, Dr Forte...", "Bests,
Alberto") nel corpo: se lo fa, il messaggio finale mostrerebbe due
chiusure in fila, quella scritta a mano seguita da quella vera.

Per evitare che questo dipenda dalla disciplina di chi scrive il
messaggio ogni singola volta, `build_message` applica
`strip_manual_closing` prima di appendere la firma: rileva un pattern di
chiusura nota (vedi `DEFAULT_CLOSING_PHRASES`: "Cordialement", "Bien
cordialement", "Bests", "Best regards", "Kind regards", "Regards",
"Cordiali saluti", "Distinti saluti", "Un cordiale saluto", con o senza
maiuscola iniziale) quando compare nell'ultimo quarto del messaggio, e
taglia da li' in poi, sia nel testo semplice sia nell'HTML. La rimozione
e' automatica e silenziosa: non blocca la chiamata, non chiede conferma.

Limiti noti di questa euristica, da tenere a mente se va estesa:

- Copre le formule effettivamente in uso su queste caselle (francese,
  italiano, inglese) piu' pochi equivalenti comuni. Una formula non
  elencata (e non passata via `closing_phrases`) non viene riconosciuta.
- Si applica solo se la formula compare nell'ultimo quarto del testo, per
  non tagliare per errore un paragrafo che cita "cordialement" a meta'
  messaggio per altri motivi. Su un messaggio breve questo puo' significare
  che una chiusura vicina al centro del testo non viene rimossa: e'
  voluto, non un bug (vedi i test in `tests/test_rules.py`).
- E' un'euristica testuale, non una comprensione del contenuto: resta
  possibile costruire un messaggio che la elude. Non e' pensata come
  misura di sicurezza, solo come rete di protezione contro l'errore piu'
  comune osservato in pratica.

## Una sola riga vuota ovunque: tra i paragrafi, e tra il corpo e la firma

Regola generale: qualunque tag di blocco (`<p>`, `<div>`, `<ul>`, `<ol>`,
`<table>`, i titoli, `<blockquote>`) porta gia' con se' il proprio
margine verticale in Gmail. Ogni `<br>` messo subito prima o subito dopo
un tag di blocco e' quindi ridondante e produce una riga vuota in piu'
rispetto a quella che il tag stesso gia' fornisce.

**Tra i paragrafi del corpo.** `wrap_html` chiama
`normalize_paragraph_spacing` prima di applicare lo stile. Questa
funzione toglie ogni `<br>` (o sequenza di `<br>`) che si trova
direttamente tra due tag di blocco di primo livello nel frammento HTML.
Un `<br>` messo a mano tra un `</p>` e il `<p>` successivo si somma al
margine gia' applicato da Gmail e produce una doppia riga vuota. La
normalizzazione non tocca un `<br>` che sta tra testo semplice e un tag
di blocco, ne' un `<br>` dentro testo non strutturato senza tag attorno.

**Tra il corpo e la firma.** Qui la storia, nel progetto originale, e'
stata piu' lunga: un primo tentativo aveva ridotto la separazione da due
`<br>` a uno solo, ragionando che le firme iniziano gia' con il proprio
distacco prima della formula di chiusura. Quel fix ha risolto il caso di
due separatori sommati, ma non il problema di fondo: quando `html_body`
finisce con un tag di blocco (`</p>`, `</div>`, ...), quel tag porta gia'
il proprio margine inferiore, quindi anche un solo `<br>` subito dopo
produce comunque una riga vuota in piu'.

La correzione definitiva e' `ends_with_block_tag`: verifica se l'ultimo
nodo di primo livello di `html_body` (spazi bianchi a parte) e' un tag di
blocco. `build_message` la usa per decidere il separatore verso la
firma: stringa vuota se `html_body` finisce in un tag di blocco (il
margine del tag e' gia' sufficiente), un `<br>` esplicito solo se
`html_body` finisce in testo semplice senza tag di blocco (in quel caso
serve ancora un ritorno a capo esplicito).

Nota pratica per chi estende queste regole: un fix su un problema di resa
visiva (spaziatura, doppioni) va verificato guardando l'email davvero
renderizzata in Gmail, non solo il testo grezzo prodotto dal codice,
perche' il rendering finale dipende anche dal comportamento di Gmail sui
tag di blocco, che il solo output testuale non mostra. Una simulazione
locale con BeautifulSoup (vedi `tests/test_rules.py`) verifica la
struttura dell'HTML prodotto, non come Gmail lo mostra davvero: resta
comunque utile prima di ogni deploy, ma non sostituisce una verifica
visiva occasionale su una bozza vera.
