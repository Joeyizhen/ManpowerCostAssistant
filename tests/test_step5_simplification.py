"""Synthetic UI checks: one ordinary allowance; PWM confined to explicit trades."""

from types import SimpleNamespace

import pytest

from future_inputs import future_method_options, pwm_trade, pwm_trade_hints
from services.models import Plan, Role


@pytest.mark.parametrize(
    "title,trade",
    [
        ("Facility Manager", None),
        ("Technician", None),
        ("M&E Engineer", None),
        ("Fire Safety Manager", None),
        ("Security Systems Engineer", None),
        ("Cleaning Supervisor", "cleaning"),
        ("Cleaner", "cleaning"),
        ("Security Officer", "security"),
        ("Lift Technician", "lift"),
        ("Escalator Technician", "lift"),
        ("Landscape Worker", "landscape"),
    ],
)
def test_pwm_discovery_is_narrow_and_never_assigns_eligibility(title, trade):
    r = Role(id="role", label=title)
    p = Plan(roles=[r])
    assert pwm_trade(r) == trade
    assert ("PWM salary progression" in future_method_options(p, r)) == bool(trade)
    assert r.pwm is None


def test_saved_pwm_setting_is_retained_for_review_after_a_title_change():
    r = SimpleNamespace(id="old", label="Facility Manager", pwm=object(), escalation_mode="assumption")
    assert "PWM salary progression" in future_method_options(Plan(), r)


# Grouped preview, save/resume and mixed PWM UI journeys supersede the former
# role-override UI checks; see test_grouped_future_journey.py.


def test_combined_trade_titles_keep_both_category_choices_without_auto_eligibility():
    role = Role(id="combined", label="Cleaning & Security team")
    assert pwm_trade_hints(role) == {"cleaning", "security"}
    assert role.label == "Cleaning & Security team" and role.pwm is None
