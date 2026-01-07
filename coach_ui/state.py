import streamlit as st


def init_state() -> None:
    defaults = {
        "page": "login",
        "logged_in": False,

        "active_call_id": None,
        "last_call_id": None,          # NEW: keep last call for post-call screen

        "live_idx": 0,
        "call_seconds": 0,
        "live_play": False,
        "live_started": False,

        "login_email": "",
        "login_password": "",          # NEW

        "post_call_sent": False,       # NEW: “sent to supervisor” UI state
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def go(page: str) -> None:
    st.session_state.page = page
    st.rerun()