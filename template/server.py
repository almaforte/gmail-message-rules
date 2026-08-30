"""
server.py (template)

Scheletro di connettore MCP per invio, bozze e risposta email via Gmail
API, con OAuth e pagina di setup. Ogni regola di formattazione (niente
trattini lunghi, niente firma duplicata, html_body obbligatorio,
spaziatura corretta) viene applicata da gmail_message_rules.build_message,
non riscritta qui: questo file si occupa solo di OAuth, Gmail API, e dei
tool MCP esposti.

Per usarlo in un nuovo repository:

1. Copia questo file e config_example.py nel tuo repository.
2. Rinomina config_example.py in config.py e personalizzalo (le tue
   caselle, le tue firme).
3. pip install -r requirements.txt (di questo repository) e
   pip install git+https://github.com/almaforte/gmail-message-rules.git
   nel tuo requirements.txt.
4. Imposta le variabili d'ambiente elencate sotto.
5. Aggiungi/adatta eventuali tool specifici del tuo progetto (allegati,
   liste, filtri) mantenendo send_email/create_draft/reply_email cosi'
   come sono: sono il punto in cui le regole vengono applicate.

Variabili d'ambiente richieste:
    GOOGLE_CLIENT_ID       ID client OAuth
    GOOGLE_CLIENT_SECRET   Segreto client OAuth
    SERVER_URL             URL pubblico di QUESTO servizio, es. https://xxx.railway.app
    ADMIN_PASSWORD         Password per accedere a /setup
    FERNET_KEY             Chiave di cifratura per i token, generata con:
                            python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    PORT                   Porta di ascolto (default 3001)
    TOKENS_FILE            Percorso del file token su un volume persistente,
                            es. /data/tokens.json

Variabili d'ambiente facoltative:
    TOKENS_DATA            Contenuto JSON dei token, usato solo come innesco
                            iniziale se TOKENS_FILE e' vuoto
"""

import base64
import contextlib
import json
import os
import secrets
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import getaddresses, formataddr
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from gmail_message_rules import build_message, HtmlBodyRequiredError

import config  # config.py, copiato e personalizzato da config_example.py

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
SERVER_URL = os.environ["SERVER_URL"].rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
FERNET_KEY = os.environ["FERNET_KEY"]

REDIRECT_URI = f"{SERVER_URL}/oauth/callback"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI],
    }
}

TOKENS_FILE = Path(os.environ.get("TOKENS_FILE", "./tokens.json"))
fernet = Fernet(FERNET_KEY.encode())


def _load_tokens() -> dict:
    if TOKENS_FILE.exists():
        content = TOKENS_FILE.read_text().strip()
        if content:
            return json.loads(content)
    raw = os.environ.get("TOKENS_DATA")
    if raw:
        tokens = json.loads(raw)
        _save_tokens(tokens)
        return tokens
    return {}


def _save_tokens(tokens: dict) -> None:
    TOKENS_FILE.write_text(json.dumps(tokens))


_tokens: dict = _load_tokens()
_pending_pkce: dict = {}


def _store_credentials(email: str, creds: Credentials) -> None:
    encrypted = fernet.encrypt(creds.to_json().encode()).decode()
    _tokens[email] = encrypted
    _save_tokens(_tokens)


def _get_credentials(email: str) -> Credentials:
    if email not in _tokens:
        raise ValueError(f"Casella '{email}' non collegata. Collegala su {SERVER_URL}/setup")
    decrypted = fernet.decrypt(_tokens[email].encode()).decode()
    creds = Credentials.from_authorized_user_info(json.loads(decrypted), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        _store_credentials(email, creds)
    return creds


def _gmail_service(email: str):
    return build("gmail", "v1", credentials=_get_credentials(email))


def _get_style(account: str) -> dict:
    from gmail_message_rules import DEFAULT_STYLE
    style = dict(config.STYLE or DEFAULT_STYLE)
    style.update(config.STYLE_OVERRIDES.get(account, {}))
    return style


# ---------------------------------------------------------------------------
# Costruzione del messaggio: le regole vengono applicate qui, tramite
# gmail_message_rules.build_message. Non riscrivere questa logica altrove:
# se serve un comportamento diverso, va cambiato nel pacchetto condiviso,
# cosi' resta coerente su tutti i repository che lo usano.
# ---------------------------------------------------------------------------


def _build_mime(
    to: str,
    subject: str,
    body: str,
    account: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
    include_signature: bool = True,
    html_body: str = "",
) -> str:
    signature_text = config.SIGNATURES_TEXT.get(account, "") if include_signature else ""
    signature_html = config.SIGNATURES_HTML.get(account, "") if include_signature else ""

    built = build_message(
        subject=subject,
        body=body,
        html_body=html_body,
        signature_text=signature_text,
        signature_html=signature_html,
        closing_phrases=config.CLOSING_PHRASES,
        style=_get_style(account),
    )

    message = MIMEMultipart("alternative")
    message.attach(MIMEText(built["text_body"], "plain"))
    message.attach(MIMEText(built["html_body"], "html"))

    message["to"] = to
    message["subject"] = built["subject"]
    if cc:
        message["cc"] = cc
    if bcc:
        message["bcc"] = bcc
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = references or in_reply_to
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


def _merge_recipients(*header_values: str, exclude: set) -> Optional[str]:
    seen = set()
    merged = []
    for name, addr in getaddresses([v for v in header_values if v]):
        key = addr.lower().strip()
        if not key or key in exclude or key in seen:
            continue
        seen.add(key)
        merged.append(formataddr((name, addr)))
    return ", ".join(merged) or None


def _reply_context(service, account: str, message_id: str, reply_all: bool = False) -> dict:
    original = service.users().messages().get(
        userId="me",
        id=message_id,
        format="metadata",
        metadataHeaders=["From", "To", "Cc", "Reply-To", "Subject", "Message-ID", "References"],
    ).execute()
    headers = {h["name"]: h["value"] for h in original["payload"]["headers"]}

    subject = headers.get("Subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    to = headers.get("Reply-To") or headers.get("From", "")

    cc = None
    if reply_all:
        to_addrs = {addr.lower() for _, addr in getaddresses([to]) if addr}
        cc = _merge_recipients(
            headers.get("To", ""),
            headers.get("Cc", ""),
            exclude={account.lower()} | to_addrs,
        )

    references = " ".join(filter(None, [headers.get("References", ""), headers.get("Message-ID", "")]))

    return {
        "to": to,
        "cc": cc,
        "subject": subject,
        "in_reply_to": headers.get("Message-ID"),
        "references": references,
        "thread_id": original["threadId"],
    }


# ---------------------------------------------------------------------------
# Strumenti MCP
# ---------------------------------------------------------------------------

_server_host = SERVER_URL.split("://", 1)[-1]

mcp = FastMCP(
    "Gmail Send",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", _server_host],
        allowed_origins=[SERVER_URL],
    ),
)


@mcp.tool()
def list_accounts() -> list:
    """Elenca le caselle collegate a questo connettore di invio."""
    return sorted(_tokens)


@mcp.tool()
def send_email(
    account: str,
    to: str,
    subject: str,
    body: str,
    html_body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
) -> dict:
    """
    Invia una nuova email da una delle caselle collegate. La firma
    ufficiale della casella (se configurata in config.py) viene aggiunta
    automaticamente.

    html_body: OBBLIGATORIO. Il messaggio viene sempre inviato in
        multipart/alternative. Non includere una formula di chiusura
        scritta a mano ne' trattini lunghi (em dash, en dash): vengono
        gestiti automaticamente da gmail_message_rules prima dell'invio.
    """
    try:
        service = _gmail_service(account)
        raw = _build_mime(to, subject, body, account, cc, bcc, html_body=html_body)
    except HtmlBodyRequiredError as exc:
        raise ValueError(str(exc))
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"id": sent["id"], "threadId": sent["threadId"], "stato": "inviata"}


@mcp.tool()
def create_draft(
    account: str,
    body: str,
    html_body: str,
    subject: Optional[str] = None,
    to: Optional[str] = None,
    cc: Optional[str] = None,
    reply_to_message_id: Optional[str] = None,
    reply_all: bool = True,
) -> dict:
    """
    Crea una bozza in una delle caselle collegate, senza inviarla.

    reply_to_message_id: se fornito, la bozza viene creata come risposta a
        quel messaggio e resta nel suo thread.
    html_body: OBBLIGATORIO, vedi send_email.
    """
    service = _gmail_service(account)

    in_reply_to = None
    references = None
    thread_id = None

    if reply_to_message_id:
        ctx = _reply_context(service, account, reply_to_message_id, reply_all=reply_all)
        to = to or ctx["to"]
        subject = subject or ctx["subject"]
        cc = cc or ctx["cc"]
        in_reply_to = ctx["in_reply_to"]
        references = ctx["references"]
        thread_id = ctx["thread_id"]

    if not to:
        raise ValueError("Serve un destinatario: passa 'to' oppure 'reply_to_message_id'.")

    try:
        raw = _build_mime(
            to, subject or "", body, account, cc,
            in_reply_to=in_reply_to, references=references, html_body=html_body,
        )
    except HtmlBodyRequiredError as exc:
        raise ValueError(str(exc))

    message_body = {"raw": raw}
    if thread_id:
        message_body["threadId"] = thread_id

    draft = service.users().drafts().create(userId="me", body={"message": message_body}).execute()
    return {
        "id": draft["id"],
        "threadId": thread_id,
        "destinatario": to,
        "copia": cc,
        "stato": "bozza creata nel thread" if thread_id else "bozza creata",
    }


@mcp.tool()
def reply_email(
    account: str,
    message_id: str,
    body: str,
    html_body: str,
    reply_all: bool = False,
) -> dict:
    """
    Risponde a un'email esistente restando nello stesso thread.

    html_body: OBBLIGATORIO, vedi send_email.
    """
    service = _gmail_service(account)
    ctx = _reply_context(service, account, message_id, reply_all=reply_all)

    try:
        raw = _build_mime(
            to=ctx["to"], subject=ctx["subject"], body=body, account=account,
            cc=ctx["cc"], in_reply_to=ctx["in_reply_to"], references=ctx["references"],
            html_body=html_body,
        )
    except HtmlBodyRequiredError as exc:
        raise ValueError(str(exc))

    sent = service.users().messages().send(
        userId="me", body={"raw": raw, "threadId": ctx["thread_id"]}
    ).execute()
    return {"id": sent["id"], "threadId": sent["threadId"], "stato": "risposta inviata"}


# ---------------------------------------------------------------------------
# App FastAPI: pagina di setup e callback OAuth, montata insieme a MCP
# ---------------------------------------------------------------------------

security = HTTPBasic()


def _check_admin(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    if not secrets.compare_digest(credentials.password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Password non valida", headers={"WWW-Authenticate": "Basic"})


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/setup", response_class=HTMLResponse)
def setup_page(_: None = Depends(_check_admin)):
    accounts = "".join(f"<li>{email}</li>" for email in sorted(_tokens)) or "<li>nessuna casella collegata</li>"
    return f"""
    <html><body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
    <h2>Gmail Send MCP &middot; caselle collegate</h2>
    <ul>{accounts}</ul>
    <p><a href="/connect">+ Collega una nuova casella</a></p>
    <hr>
    <p>Per persistere le connessioni tra un redeploy e l'altro,
    copia questo valore nella variabile d'ambiente <code>TOKENS_DATA</code>:</p>
    <textarea style="width:100%; height:120px;" readonly>{json.dumps(_tokens)}</textarea>
    </body></html>
    """


@app.get("/connect")
def connect(_: None = Depends(_check_admin)):
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    if flow.code_verifier:
        _pending_pkce[state] = flow.code_verifier
    return RedirectResponse(auth_url)


@app.get("/oauth/callback")
def oauth_callback(request: Request):
    state = request.query_params.get("state")
    flow = Flow.from_client_config(
        CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI,
        state=state, code_verifier=_pending_pkce.pop(state, None),
    )
    # Molti PaaS (Railway incluso) terminano https sul proprio proxy e
    # inoltrano al servizio in http semplice: senza questa correzione la
    # libreria Google rifiuta di completare lo scambio del codice.
    authorization_response = str(request.url).replace("http://", "https://", 1)
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials

    oauth2 = build("oauth2", "v2", credentials=creds)
    email = oauth2.userinfo().get().execute()["email"]

    _store_credentials(email, creds)
    return RedirectResponse("/setup")


app.mount("/", mcp.streamable_http_app())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 3001)),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
