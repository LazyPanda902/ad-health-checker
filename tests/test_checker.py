"""Tests for ad_health_checker core logic."""

from __future__ import annotations

import json
import socket
import sys
from unittest.mock import MagicMock, patch

import pytest

from ad_health_checker.checker import (
    AD_PORTS,
    CheckResult,
    HealthReport,
    Status,
    build_report,
    check_dns_resolution,
    check_kerberos_reachability,
    check_ldap_banner,
    check_port,
    check_reverse_dns,
    format_report,
    format_report_json,
    run_controller_checks,
)
from ad_health_checker.cli import build_parser, _cmd_ports


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

def test_status_values():
    assert Status.OK.value == "OK"
    assert Status.WARN.value == "WARN"
    assert Status.FAIL.value == "FAIL"
    assert Status.SKIP.value == "SKIP"


def test_status_is_str():
    assert isinstance(Status.OK, str)


# ---------------------------------------------------------------------------
# AD_PORTS constant
# ---------------------------------------------------------------------------

def test_ad_ports_has_expected_services():
    for svc in ("kerberos", "ldap", "smb", "ldaps", "dns"):
        assert svc in AD_PORTS

def test_kerberos_port():
    assert AD_PORTS["kerberos"] == 88

def test_ldap_port():
    assert AD_PORTS["ldap"] == 389

def test_smb_port():
    assert AD_PORTS["smb"] == 445


# ---------------------------------------------------------------------------
# CheckResult dataclass
# ---------------------------------------------------------------------------

def test_check_result_defaults():
    r = CheckResult(name="test", target="host", status=Status.OK, detail="fine")
    assert r.elapsed_ms == 0.0

def test_check_result_fields():
    r = CheckResult(name="dns_resolution", target="dc1.corp.local", status=Status.FAIL, detail="nope", elapsed_ms=12.5)
    assert r.name == "dns_resolution"
    assert r.target == "dc1.corp.local"
    assert r.status == Status.FAIL
    assert r.detail == "nope"
    assert r.elapsed_ms == 12.5


# ---------------------------------------------------------------------------
# HealthReport
# ---------------------------------------------------------------------------

def _make_report(*statuses: Status) -> HealthReport:
    report = HealthReport(domain="corp.local", controllers=["dc1"])
    for i, s in enumerate(statuses):
        report.results.append(CheckResult(name=f"check_{i}", target="dc1", status=s, detail=""))
    return report


def test_health_report_summary_empty():
    report = HealthReport(domain="corp.local", controllers=[])
    s = report.summary()
    assert s["OK"] == 0
    assert s["FAIL"] == 0

def test_health_report_summary_counts():
    report = _make_report(Status.OK, Status.OK, Status.FAIL, Status.WARN)
    s = report.summary()
    assert s["OK"] == 2
    assert s["FAIL"] == 1
    assert s["WARN"] == 1

def test_overall_status_ok():
    assert _make_report(Status.OK, Status.OK).overall_status() == Status.OK

def test_overall_status_warn():
    assert _make_report(Status.OK, Status.WARN).overall_status() == Status.WARN

def test_overall_status_fail_beats_warn():
    assert _make_report(Status.WARN, Status.FAIL).overall_status() == Status.FAIL


# ---------------------------------------------------------------------------
# check_dns_resolution
# ---------------------------------------------------------------------------

def test_check_dns_resolution_ok():
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [(None, None, None, None, ("127.0.0.1", 0))]
        result = check_dns_resolution("localhost")
    assert result.status == Status.OK
    assert result.name == "dns_resolution"
    assert "127.0.0.1" in result.detail

def test_check_dns_resolution_fail():
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name not found")):
        result = check_dns_resolution("no-such-host.invalid")
    assert result.status == Status.FAIL
    assert "DNS lookup failed" in result.detail
    assert result.target == "no-such-host.invalid"

def test_check_dns_resolution_elapsed_ms_non_negative():
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [(None, None, None, None, ("10.0.0.1", 0))]
        result = check_dns_resolution("dc1")
    assert result.elapsed_ms >= 0.0


# ---------------------------------------------------------------------------
# check_port
# ---------------------------------------------------------------------------

def test_check_port_ok():
    mock_sock = MagicMock()
    mock_sock.__enter__ = lambda s: s
    mock_sock.__exit__ = MagicMock(return_value=False)
    with patch("socket.create_connection", return_value=mock_sock):
        result = check_port("dc1", 389, "ldap")
    assert result.status == Status.OK
    assert result.name == "port_ldap"
    assert result.target == "dc1:389"

def test_check_port_refused():
    with patch("socket.create_connection", side_effect=ConnectionRefusedError("refused")):
        result = check_port("dc1", 389, "ldap")
    assert result.status == Status.FAIL
    assert "389" in result.detail

def test_check_port_timeout():
    with patch("socket.create_connection", side_effect=TimeoutError("timed out")):
        result = check_port("dc1", 88, "kerberos")
    assert result.status == Status.WARN
    assert "88" in result.detail


# ---------------------------------------------------------------------------
# check_reverse_dns
# ---------------------------------------------------------------------------

def test_check_reverse_dns_ok():
    with patch("socket.gethostbyaddr", return_value=("dc1.corp.local", [], ["10.0.0.1"])):
        result = check_reverse_dns("10.0.0.1")
    assert result.status == Status.OK
    assert "dc1.corp.local" in result.detail

def test_check_reverse_dns_no_ptr():
    with patch("socket.gethostbyaddr", side_effect=socket.herror("no PTR")):
        result = check_reverse_dns("10.0.0.99")
    assert result.status == Status.WARN
    assert "No PTR record" in result.detail


# ---------------------------------------------------------------------------
# check_ldap_banner
# ---------------------------------------------------------------------------

def test_check_ldap_banner_ok():
    mock_sock = MagicMock()
    mock_sock.__enter__ = lambda s: s
    mock_sock.__exit__ = MagicMock(return_value=False)
    mock_sock.recv.return_value = b"\x30\x0c\x02\x01\x01\x61\x07\x0a\x01\x00\x04\x00\x04\x00"
    with patch("socket.create_connection", return_value=mock_sock):
        result = check_ldap_banner("dc1")
    assert result.status == Status.OK
    assert "389" in result.target

def test_check_ldap_banner_empty_response():
    mock_sock = MagicMock()
    mock_sock.__enter__ = lambda s: s
    mock_sock.__exit__ = MagicMock(return_value=False)
    mock_sock.recv.return_value = b""
    with patch("socket.create_connection", return_value=mock_sock):
        result = check_ldap_banner("dc1")
    assert result.status == Status.WARN

def test_check_ldap_banner_fail():
    with patch("socket.create_connection", side_effect=ConnectionRefusedError("refused")):
        result = check_ldap_banner("dc1")
    assert result.status == Status.FAIL
    assert "LDAP probe failed" in result.detail


# ---------------------------------------------------------------------------
# check_kerberos_reachability
# ---------------------------------------------------------------------------

def test_check_kerberos_reachability_delegates_to_check_port():
    with patch("ad_health_checker.checker.check_port") as mock_cp:
        mock_cp.return_value = CheckResult("port_kerberos", "dc1:88", Status.OK, "ok")
        result = check_kerberos_reachability("dc1")
    mock_cp.assert_called_once_with("dc1", 88, "kerberos")
    assert result.status == Status.OK


# ---------------------------------------------------------------------------
# run_controller_checks
# ---------------------------------------------------------------------------

def test_run_controller_checks_skips_on_dns_fail():
    with patch("ad_health_checker.checker.check_dns_resolution") as mock_dns:
        mock_dns.return_value = CheckResult("dns_resolution", "bad.host", Status.FAIL, "failed")
        results = run_controller_checks("bad.host")
    assert any(r.status == Status.SKIP for r in results)
    assert any(r.name == "port_checks_skipped" for r in results)

def test_run_controller_checks_skip_ldap_probe():
    with patch("ad_health_checker.checker.check_dns_resolution") as mock_dns, \
         patch("ad_health_checker.checker.check_port") as mock_port, \
         patch("socket.getaddrinfo", return_value=[]):
        mock_dns.return_value = CheckResult("dns_resolution", "dc1", Status.OK, "10.0.0.1")
        mock_port.return_value = CheckResult("port_kerberos", "dc1:88", Status.OK, "open")
        results = run_controller_checks("dc1", check_ports_list=["kerberos"], skip_ldap_probe=True)
    names = [r.name for r in results]
    assert "ldap_banner" not in names

def test_run_controller_checks_includes_ldap_probe_by_default():
    with patch("ad_health_checker.checker.check_dns_resolution") as mock_dns, \
         patch("ad_health_checker.checker.check_port") as mock_port, \
         patch("ad_health_checker.checker.check_ldap_banner") as mock_ldap, \
         patch("socket.getaddrinfo", return_value=[]):
        mock_dns.return_value = CheckResult("dns_resolution", "dc1", Status.OK, "10.0.0.1")
        mock_port.return_value = CheckResult("port_kerberos", "dc1:88", Status.OK, "open")
        mock_ldap.return_value = CheckResult("ldap_banner", "dc1:389", Status.OK, "ok")
        run_controller_checks("dc1", check_ports_list=["kerberos"])
    mock_ldap.assert_called_once_with("dc1")


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

def test_build_report_structure():
    with patch("ad_health_checker.checker.run_controller_checks") as mock_rc:
        mock_rc.return_value = [CheckResult("dns_resolution", "dc1", Status.OK, "ok")]
        report = build_report("corp.local", ["dc1"])
    assert report.domain == "corp.local"
    assert report.controllers == ["dc1"]
    assert len(report.results) == 1
    assert report.generated_at != ""

def test_build_report_calls_each_controller():
    with patch("ad_health_checker.checker.run_controller_checks") as mock_rc:
        mock_rc.return_value = []
        build_report("corp.local", ["dc1", "dc2"])
    assert mock_rc.call_count == 2


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------

def test_format_report_contains_domain():
    report = _make_report(Status.OK)
    report.generated_at = "2026-01-01T00:00:00+00:00"
    text = format_report(report)
    assert "corp.local" in text

def test_format_report_contains_summary_line():
    report = _make_report(Status.OK, Status.FAIL)
    report.generated_at = "2026-01-01T00:00:00+00:00"
    text = format_report(report)
    assert "Summary:" in text
    assert "Overall:" in text

def test_format_report_verbose_includes_timing():
    report = HealthReport(domain="corp.local", controllers=["dc1"], generated_at="2026-01-01T00:00:00+00:00")
    report.results.append(CheckResult("dns_resolution", "dc1", Status.OK, "fine", elapsed_ms=5.5))
    text = format_report(report, verbose=True)
    assert "5.5" in text

def test_format_report_fail_detail_shown():
    report = HealthReport(domain="corp.local", controllers=["dc1"], generated_at="2026-01-01T00:00:00+00:00")
    report.results.append(CheckResult("port_ldap", "dc1:389", Status.FAIL, "connection refused"))
    text = format_report(report)
    assert "connection refused" in text


# ---------------------------------------------------------------------------
# format_report_json
# ---------------------------------------------------------------------------

def test_format_report_json_is_valid_json():
    report = _make_report(Status.OK)
    report.generated_at = "2026-01-01T00:00:00+00:00"
    data = json.loads(format_report_json(report))
    assert data["domain"] == "corp.local"
    assert "results" in data
    assert "summary" in data
    assert "overall" in data

def test_format_report_json_result_fields():
    report = HealthReport(domain="corp.local", controllers=["dc1"], generated_at="2026-01-01T00:00:00+00:00")
    report.results.append(CheckResult("dns_resolution", "dc1", Status.OK, "fine", elapsed_ms=3.0))
    data = json.loads(format_report_json(report))
    r = data["results"][0]
    assert r["name"] == "dns_resolution"
    assert r["status"] == "OK"
    assert r["elapsed_ms"] == 3.0


# ---------------------------------------------------------------------------
# CLI — build_parser
# ---------------------------------------------------------------------------

def test_build_parser_constructs_without_error():
    parser = build_parser()
    assert parser is not None

def test_build_parser_has_subcommands():
    parser = build_parser()
    ns = parser.parse_args(["dns", "dc1.corp.local"])
    assert ns.command == "dns"

def test_parser_report_required_args():
    parser = build_parser()
    ns = parser.parse_args(["report", "--domain=corp.local", "--controllers=dc1,dc2"])
    assert ns.domain == "corp.local"
    assert ns.controllers == "dc1,dc2"

def test_parser_report_no_ldap_probe_flag():
    parser = build_parser()
    ns = parser.parse_args(["report", "--domain=corp.local", "--controllers=dc1", "--no-ldap-probe"])
    assert ns.no_ldap_probe is True

def test_parser_report_json_flag():
    parser = build_parser()
    ns = parser.parse_args(["report", "--domain=corp.local", "--controllers=dc1", "--json"])
    assert ns.json is True

def test_parser_report_verbose_flag():
    parser = build_parser()
    ns = parser.parse_args(["report", "--domain=corp.local", "--controllers=dc1", "--verbose"])
    assert ns.verbose is True

def test_parser_dns_positional_hosts():
    parser = build_parser()
    ns = parser.parse_args(["dns", "dc1", "dc2"])
    assert ns.hosts == ["dc1", "dc2"]

def test_parser_ports_with_services():
    parser = build_parser()
    ns = parser.parse_args(["ports", "dc1", "--services=kerberos,ldap"])
    assert ns.services == "kerberos,ldap"

def test_parser_kerberos_subcommand():
    parser = build_parser()
    ns = parser.parse_args(["kerberos", "dc1.corp.local"])
    assert ns.command == "kerberos"
    assert ns.hosts == ["dc1.corp.local"]

def test_parser_ldap_subcommand():
    parser = build_parser()
    ns = parser.parse_args(["ldap", "dc1.corp.local"])
    assert ns.command == "ldap"

def test_parser_func_set_for_report():
    from ad_health_checker.cli import _cmd_report
    parser = build_parser()
    ns = parser.parse_args(["report", "--domain=corp.local", "--controllers=dc1"])
    assert ns.func is _cmd_report

def test_parser_func_set_for_dns():
    from ad_health_checker.cli import _cmd_dns
    parser = build_parser()
    ns = parser.parse_args(["dns", "dc1"])
    assert ns.func is _cmd_dns


# ---------------------------------------------------------------------------
# CLI — parser syntax errors raise SystemExit(2)
# ---------------------------------------------------------------------------

def test_parser_no_subcommand_raises_system_exit():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])
    assert exc_info.value.code == 2

def test_parser_report_missing_domain_raises_system_exit():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["report", "--controllers=dc1"])
    assert exc_info.value.code == 2

def test_parser_report_missing_controllers_raises_system_exit():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["report", "--domain=corp.local"])
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# CLI — application-level validation (_cmd_ports unknown service)
# ---------------------------------------------------------------------------

def test_cmd_ports_unknown_service_returns_2(capsys):
    parser = build_parser()
    ns = parser.parse_args(["ports", "dc1", "--services=notaservice"])
    result = _cmd_ports(ns)
    assert result == 2
    captured = capsys.readouterr()
    assert "unknown service" in captured.err


# ---------------------------------------------------------------------------
# CLI — main entry point
# ---------------------------------------------------------------------------

def test_main_dns_exits_cleanly(monkeypatch):
    from ad_health_checker.cli import main
    with patch("ad_health_checker.checker.check_dns_resolution") as mock_dns:
        mock_dns.return_value = CheckResult("dns_resolution", "localhost", Status.OK, "127.0.0.1")
        with pytest.raises(SystemExit) as exc_info:
            main(["dns", "localhost"])
    assert exc_info.value.code == 0

def test_main_dns_fail_exits_nonzero():
    from ad_health_checker.cli import main
    with patch("ad_health_checker.checker.check_dns_resolution") as mock_dns:
        mock_dns.return_value = CheckResult("dns_resolution", "bad.host", Status.FAIL, "failed")
        with pytest.raises(SystemExit) as exc_info:
            main(["dns", "bad.host"])
    assert exc_info.value.code == 1
