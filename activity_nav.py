"""Activity navigation retains session drafts without saving or confirming them."""

from copy import deepcopy

import streamlit as st

ACTIVITIES = {
    "budgeting": ("Manpower budgeting", "Build or review a manpower budget."),
    "tender": ("Tender evaluation", "Review tender submissions against a budget or other tenderers."),
}
TASKS = {
    1: ("budgeting", "Build a new budget"),
    2: ("budgeting", "Review a proposed budget"),
    3: ("tender", "Compare submissions against an approved budget"),
    4: ("tender", "Compare tenderer proposals"),
}


def retained_key(key):
    """Register value inputs only; never restore button events or upload handles."""
    track = st.session_state.get("selected_track")
    registered = st.session_state.setdefault("activity_input_keys", {})
    keys = registered.setdefault(track, set())
    keys.add(key)
    return key


def leave_task(change_activity=False):
    track = st.session_state.get("selected_track")
    if track not in TASKS:
        return
    registered = st.session_state.get("activity_input_keys", {}).get(track, set())
    st.session_state.setdefault("activity_input_drafts", {})[track] = {
        key: deepcopy(st.session_state[key]) for key in registered if key in st.session_state
    }
    st.session_state.selected_activity = None if change_activity else TASKS[track][0]
    st.session_state.selected_track = None


def enter_task(track):
    for key, value in st.session_state.get("activity_input_drafts", {}).get(track, {}).items():
        if key not in st.session_state:
            st.session_state[key] = deepcopy(value)
    st.session_state.selected_activity = TASKS[track][0]
    st.session_state.selected_track = track


def reset_task_inputs(track):
    """A restored project supplies its own defaults, rather than the previous draft's widgets."""
    st.session_state.activity_input_reset = track


def show_activity_options():
    reset = st.session_state.pop("activity_input_reset", None)
    if reset is not None:
        for key in st.session_state.get("activity_input_keys", {}).get(reset, set()):
            st.session_state.pop(key, None)
        st.session_state.get("activity_input_drafts", {}).pop(reset, None)
    if st.session_state.get("selected_track") is not None:
        return
    activity = st.session_state.get("selected_activity")
    st.caption("FM MANPOWER COST ASSISTANT")
    if activity not in ACTIVITIES:
        st.title("What would you like to do?")
        for column, (key, (title, description)) in zip(st.columns(2), ACTIVITIES.items(), strict=True):
            with column.container(border=True):
                st.subheader(title)
                st.write(description)
                if st.button(title, key="activity_" + key, type="primary", width="stretch"):
                    st.session_state.selected_activity = key
                    st.rerun()
    else:
        st.title(ACTIVITIES[activity][0])
        if st.button("Change activity", key="activity_change_options"):
            st.session_state.selected_activity = None
            st.rerun()
        choices = [(track, title) for track, (group, title) in TASKS.items() if group == activity]
        descriptions = {
            1: "Start with your project and proposed manpower, then calculate the budget.",
            2: "Add an existing proposal, check its figures and assumptions, then review the budget.",
            3: "Use standalone verified schedules or the labelled example; live budget transfer is unavailable.",
            4: "Compare proposals with historical references. Direct comparison between tenderers is not yet available.",
        }
        for column, (track, title) in zip(st.columns(2), choices, strict=True):
            with column.container(border=True):
                st.subheader(title)
                st.write(descriptions[track])
                st.button(
                    title,
                    key=f"choose_track_{track}",
                    on_click=enter_task,
                    args=(track,),
                    type="primary",
                    width="stretch",
                )
        if activity == "tender":
            st.caption("Historical data management — Planned.")
    st.caption(
        "Drafts stay in this session when you change activity. Save or download work to keep it for later."
    )
    st.stop()


def render_navigation(track):
    activity, title = TASKS[track]
    st.caption(ACTIVITIES[activity][0] + " · " + title)
    back, change = st.columns(2)
    back.button(
        "Back to " + ("budgeting" if activity == "budgeting" else "tender evaluation") + " options",
        key="activity_back",
        on_click=leave_task,
        width="stretch",
    )
    change.button(
        "Change activity",
        key="activity_change",
        on_click=leave_task,
        args=(True,),
        width="stretch",
    )
