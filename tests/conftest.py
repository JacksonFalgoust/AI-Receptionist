import pytest

from app import config


@pytest.fixture(autouse=True)
def _no_guide_warmup(monkeypatch):
    # The startup warm-up would hit a real GuideAnts; tests never should.
    monkeypatch.setattr(config, "GUIDE_WARMUP_ON_STARTUP", False)
