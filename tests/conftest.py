"""Shared pytest fixtures for the bambu-cli suite."""

import pytest

from bambu_cli import context


@pytest.fixture(autouse=True)
def _reset_runtime_context():
    """Isolate the process-wide RuntimeContext between tests.

    ``main()`` and some tests install a context via ``context.set_current()``;
    reset it around every test so a pinned context can't leak into a later test
    that relies on reading the (patched) module-global fallback.
    """
    context.set_current(None)
    yield
    context.set_current(None)
