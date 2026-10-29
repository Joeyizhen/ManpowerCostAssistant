"""Compact reference bars; exact inputs remain the authoritative selected values."""

import html
import math

import streamlit as st


def bar_domain(lower, upper, selected):
    values = [float(v) for v in (lower, upper, selected) if v is not None and math.isfinite(float(v))]
    low, high = min(values), max(values)
    return (low, high if high > low else low + 0.01)


def reference_bar(
    label,
    key,
    selected,
    lower,
    average,
    upper,
    on_change,
    args,
    percent=False,
    disabled=False,
    average_label="Reference average",
    range_label=None,
):
    low, high = bar_domain(lower, upper, selected)
    # Do not clip an exact override to a reference band. The wider selection
    # domain includes that override while the labelled evidence band is fixed.
    current = float(selected if selected is not None else average)
    st.session_state[key] = current
    with st.container(key=key + "_visual"):
        st.markdown(
            "<style>[data-testid='stSliderThumbValue'],[data-testid='stThumbValue']"
            "{visibility:hidden}</style>",
            unsafe_allow_html=True,
        )
        st.slider(
            label,
            min_value=float(low),
            max_value=float(high),
            step=0.01,
            key=key,
            label_visibility="collapsed",
            on_change=on_change,
            args=args,
            disabled=disabled,
            help="Select on the bar or enter an exact value below. The evidence range is not a limit.",
        )
        position = max(0, min(100, 100 * (average - low) / (high - low)))
        suffix = "%" if percent else " SGD"
        label_shift = "0%" if position < 25 else "-100%" if position > 75 else "-50%"
        st.markdown(
            f'<div style="position:relative;height:2.5rem;font-size:.8rem">'
            f'<span style="position:absolute;left:{position:.3f}%;transform:translateX(-50%)">◆</span>'
            f'<span style="position:absolute;top:1rem;left:{position:.3f}%;transform:translateX({label_shift});white-space:nowrap">'
            f"{html.escape(average_label)} {html.escape(f'{average:,.2f}{suffix}')}</span></div>",
            unsafe_allow_html=True,
        )
    st.caption(
        f"{range_label or ('Lower / higher allowance' if percent else 'Comparable reference range')}: {lower:,.2f}–{upper:,.2f}{suffix}"
    )


def unavailable_bar():
    # No arbitrary market bounds, average marker or zero recommendation when
    # backend evidence is unavailable. This rail is intentionally not editable.
    st.markdown(
        '<div role="img" aria-label="Database rate reference unavailable" '
        'style="height:5px;background:#d7dfe5;border-radius:3px;margin:12px 0"></div>',
        unsafe_allow_html=True,
    )
    st.caption("Database recommendation unavailable. Enter your monthly budget allowance.")
