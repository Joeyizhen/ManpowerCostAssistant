"""Select callback ownership without swapping or overwriting the Track 1 draft."""

import streamlit as st


def current_plan():
    if st.session_state.get("selected_track") == 2 and st.session_state.get("proposal") is not None:
        return st.session_state.proposal.plan
    return st.session_state.plan


def sync_controls(prefix, signature, values):
    import ui_drafts

    missing = any(prefix + suffix not in st.session_state for suffix in values)
    if st.session_state.get(prefix + "_model") != signature or missing:
        for suffix, value in values.items():
            st.session_state[prefix + suffix] = value
        st.session_state[prefix + "_model"] = signature
        if missing:
            st.session_state.pop(prefix + "_ui_draft_restored", None)
    ui_drafts.restore_controls_after_sync(current_plan(), prefix)
