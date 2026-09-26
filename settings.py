"""Configurazione della dashboard + helper donazioni."""
import os

import streamlit as st

GOAL = 1_000_000
MILESTONE_STEP = 500
GROUP_START_STR = "2025-06-11"
TZ = "Europe/Rome"
DB_PATH = "1m_beers.db"
PHOTO_DIR = "photo_folder"
ORANGE = "#FFA500"

NICKNAMES = {
    "+39 *** 2936": "Frank 👑",
    "+49 *** 8462": "Ernesto Freyberg",
    "+49 *** 3870": "Anton Freyberg",
    "+41 *** 5011": "Constantin Huet",
    "+33 *** 2961": "Adhemar",
}


def cfg(key, default=None):
    """Legge da variabili d'ambiente o da st.secrets (se esistono)."""
    if os.getenv(key):
        return os.getenv(key)
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


STRIPE_LINK = cfg("STRIPE_LINK", "https://buy.stripe.com/dRm8wHbyFdS90ss1Fe6EU00")
PAYPAL_LINK = cfg("PAYPAL_LINK")
BMC_LINK = cfg("BUYMEACOFFEE_LINK")
PHOTO_BASE_URL = cfg("PHOTO_BASE_URL")                  # es. https://mio-nas.example.com/beers
MONTHLY_COSTS_EUR = cfg("MONTHLY_COSTS_EUR")            # es. 25
DONATED_THIS_MONTH_EUR = cfg("DONATED_THIS_MONTH_EUR")  # es. 12
SUPPORTERS = [s.strip() for s in str(cfg("SUPPORTERS", "") or "").split(",") if s.strip()]
PINT_PRICE_EUR = float(cfg("PINT_PRICE_EUR", 5.5) or 5.5)

CSS = """
<style>
div[data-testid="stMetric"] {
    background-color: rgba(255,165,0,.05); border: 1px solid rgba(255,165,0,.2);
    padding: 8px 14px; border-radius: 10px;
}
.potd-card {border-radius: 14px; padding: 22px; text-align: center;
            background: linear-gradient(135deg, rgba(255,165,0,.20), rgba(255,215,0,.04));
            border: 1px solid rgba(255,165,0,.35);}
.potd-emoji {font-size: 72px; line-height: 1.1;}
.donate-box {border-radius: 12px; padding: 14px 18px; border: 1px dashed rgba(255,165,0,.6);
             background: rgba(255,165,0,.06);}
</style>
"""


def donate_url(source):
    """client_reference_id: nel pannello Stripe vedi da quale bottone arriva ogni donazione."""
    sep = "&" if "?" in STRIPE_LINK else "?"
    return f"{STRIPE_LINK}{sep}client_reference_id=dashboard_{source}"


def donate_buttons(source, label="🍻 Buy the Dev a Pint", primary=True):
    st.link_button(label, donate_url(source), type="primary" if primary else "secondary", width="stretch")
    extra = [(l, u) for l, u in (("☕ Buy Me a Coffee", BMC_LINK), ("💙 PayPal", PAYPAL_LINK)) if u]
    if extra:
        for c, (l, u) in zip(st.columns(len(extra)), extra):
            c.link_button(l, u, width="stretch")


def photo_source(nome_file):
    """Percorso locale della foto, oppure URL remoto se PHOTO_BASE_URL è configurato."""
    name = str(nome_file).strip()
    local = os.path.join(PHOTO_DIR, name)
    if os.path.exists(local):
        return local
    if PHOTO_BASE_URL:
        return f"{PHOTO_BASE_URL.rstrip('/')}/{name}"
    return None
