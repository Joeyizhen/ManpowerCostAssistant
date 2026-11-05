"""Keep legacy fixture tests independent of the locally activated private dataset."""

import pytest


@pytest.fixture(autouse=True)
def reference_isolation(monkeypatch):
    monkeypatch.setenv("MANPOWER_REFERENCE_SOURCE", "synthetic")
    from services.evidence import load_records

    load_records()
