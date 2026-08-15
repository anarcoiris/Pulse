"""
test_freerouting_bridge.py
==========================
Unit tests for bridge/freerouting_bridge.py
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from bridge.freerouting_bridge import FreeRoutingBridge, FreeRoutingResult

def test_freerouting_bridge_init():
    bridge = FreeRoutingBridge(freerouting_jar_path="/tmp/freerouting.jar")
    assert bridge.jar_path == "/tmp/freerouting.jar"

def test_run_freerouting_missing_dsn():
    bridge = FreeRoutingBridge()
    res = bridge.run_freerouting(Path("/nonexistent/board.dsn"))
    assert not res.success
    assert res.exit_code == 1
    assert "DSN file not found" in res.message

@patch("subprocess.run")
def test_export_dsn_mock(mock_run, tmp_path):
    pcb_file = tmp_path / "board.kicad_pcb"
    pcb_file.write_text("(kicad_pcb)")
    dsn_file = tmp_path / "board.dsn"
    dsn_file.write_text("(dsn)")

    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    bridge = FreeRoutingBridge()
    result_dsn = bridge.export_dsn(pcb_file, dsn_file)
    assert result_dsn == dsn_file
    mock_run.assert_called_once()
