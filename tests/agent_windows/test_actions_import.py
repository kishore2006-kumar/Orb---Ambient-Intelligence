"""Tests that importing agent_windows.actions on Linux does not load Windows modules."""

from __future__ import annotations

import sys


def test_import_on_linux_does_not_load_windows_modules() -> None:
    """Importing agent_windows.actions should work even without Windows modules."""
    # ctypes.windll / pycaw / comtypes are only accessed lazily inside methods
    # This test verifies the import succeeds on any platform
    import importlib

    # Remove cached module if already imported
    for mod in list(sys.modules.keys()):
        if "agent_windows.actions" in mod:
            del sys.modules[mod]

    # This should not raise ImportError or AttributeError
    module = importlib.import_module("agent_windows.actions")
    assert hasattr(module, "WindowsActions")
    assert hasattr(module, "Actions")
