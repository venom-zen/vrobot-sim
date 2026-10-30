"""Skip the web suite when the optional ``web`` extra is not installed."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
