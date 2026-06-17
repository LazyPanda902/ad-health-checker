"""Core AD health checking routines using Python stdlib only."""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


# Well-known ports used by Active Directory services
AD_PORTS: dict[str, int] = {
    "kerberos": 88,
    "ldap": 389,
    "smb": 445,
    "ldap_gc": 3268,
    "ldaps": 636,
    "ldaps_gc": 3269,
    "dns": 53,
    "rpc_endpoint_mapper": 135,
}

CONNECT_TIMEOUT = 3.0  # seconds per port probe


class Status(str, Enum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class CheckResult:
    name: str
    target: str
    status: Status
    detail: str
    elapsed_ms: float = 0.0


@dataclass
class HealthReport:
    domain: str
    controllers: list[str]
    results: list[CheckResult] = field(default_factory=list)
    generated_at: str = ""

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {s.value: 0 for s in Status}
        for r in self.results:
            counts[r.status.value] += 1
        return counts

    def overall_status(self) -> Status:
        summary = self.summary()
        if summary[Status.FAIL.value] > 0:
            return Status.FAIL
        if summary[Status.WARN.value] > 0:
            return Status.WARN
        return Status.OK


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_dns_resolution(host: str) -> CheckResult:
    """Resolve a hostname and return the IP addresses found."""
    t0 = time.monotonic()
    try:
        addrs = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        ips = sorted({a[4][0] for a in addrs})
        elapsed = (time.monotonic() - t0) * 1000
        return CheckResult(
            name="dns_resolution",
            target=host,
            status=Status.OK,
            detail=f"Resolved to: {', '.join(ips)}",
            elapsed_ms=round(elapsed, 2),
        )
    except socket.gaierror as exc:
        elapsed = (time.monotonic() - t0) * 1000
        return CheckResult(
            name="dns_resolution",
            target=host,
            status=Status.FAIL,
            detail=f"DNS lookup failed: {exc}",
            elapsed_ms=round(elapsed, 2),
        )


def check_port(host: str, port: int, service: str) -> CheckResult:
    """Attempt a TCP connection to verify a service port is reachable."""
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT):
            elapsed = (time.monotonic() - t0) * 1000
            return CheckResult(
                name=f"port_{service}",
                target=f"{host}:{port}",
                status=Status.OK,
                detail=f"{service.upper()} port {port} is reachable",
                elapsed_ms=round(elapsed, 2),
            )
    except (ConnectionRefusedError, TimeoutError, OSError) as exc:
        elapsed = (time.monotonic() - t0) * 1000
        status = Status.FAIL if isinstance(exc, ConnectionRefusedError) else Status.WARN
        return CheckResult(
            name=f"port_{service}",
            target=f"{host}:{port}",
            status=status,
            detail=f"{service.upper()} port {port} unreachable: {exc}",
            elapsed_ms=round(elapsed, 2),
        )


def check_reverse_dns(ip: str) -> CheckResult:
    """Verify that an IP address resolves back to a hostname (PTR record)."""
    t0 = time.monotonic()
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        elapsed = (time.monotonic() - t0) * 1000
        return CheckResult(
            name="reverse_dns",
            target=ip,
            status=Status.OK,
            detail=f"PTR record: {hostname}",
            elapsed_ms=round(elapsed, 2),
        )
    except socket.herror as exc:
        elapsed = (time.monotonic() - t0) * 1000
        return CheckResult(
            name="reverse_dns",
            target=ip,
            status=Status.WARN,
            detail=f"No PTR record: {exc}",
            elapsed_ms=round(elapsed, 2),
        )


def check_ldap_banner(host: str, port: int = 389) -> CheckResult:
    """
    Perform a minimal LDAP root DSE probe over a raw TCP socket.

    Sends a valid BER-encoded anonymous bind request and checks for any
    response bytes, which confirms an LDAP listener is active.
    """
    # Minimal LDAPMessage: bindRequest anonymous (no auth)
    # Sequence { INTEGER 1, [APPLICATION 0] { INTEGER 3, OCTET STRING "", [0] "" } }
    bind_request = bytes([
        0x30, 0x0c,          # SEQUENCE, length 12
        0x02, 0x01, 0x01,    # INTEGER 1 (messageID)
        0x60, 0x07,          # [APPLICATION 0] bindRequest, length 7
        0x02, 0x01, 0x03,    # INTEGER 3 (LDAP version)
        0x04, 0x00,          # OCTET STRING "" (DN)
        0x80, 0x00,          # [0] "" (simple auth, empty password)
    ])
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT) as sock:
            sock.sendall(bind_request)
            response = sock.recv(16)
            elapsed = (time.monotonic() - t0) * 1000
            if response:
                return CheckResult(
                    name="ldap_banner",
                    target=f"{host}:{port}",
                    status=Status.OK,
                    detail=f"LDAP listener responded ({len(response)} bytes)",
                    elapsed_ms=round(elapsed, 2),
                )
            return CheckResult(
                name="ldap_banner",
                target=f"{host}:{port}",
                status=Status.WARN,
                detail="LDAP connection succeeded but no response data",
                elapsed_ms=round(elapsed, 2),
            )
    except (ConnectionRefusedError, TimeoutError, OSError) as exc:
        elapsed = (time.monotonic() - t0) * 1000
        return CheckResult(
            name="ldap_banner",
            target=f"{host}:{port}",
            status=Status.FAIL,
            detail=f"LDAP probe failed: {exc}",
            elapsed_ms=round(elapsed, 2),
        )


def check_kerberos_reachability(host: str) -> CheckResult:
    """Check whether the Kerberos KDC port is open (port 88 TCP)."""
    return check_port(host, 88, "kerberos")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_controller_checks(
    host: str,
    *,
    check_ports_list: Sequence[str] | None = None,
    skip_ldap_probe: bool = False,
) -> list[CheckResult]:
    """Run all checks against a single domain controller hostname."""
    results: list[CheckResult] = []

    dns_result = check_dns_resolution(host)
    results.append(dns_result)

    if dns_result.status == Status.FAIL:
        results.append(CheckResult(
            name="port_checks_skipped",
            target=host,
            status=Status.SKIP,
            detail="Skipped port checks because DNS resolution failed",
        ))
        return results

    ports_to_check = check_ports_list or list(AD_PORTS.keys())
    checked_ports: set[int] = set()
    for service in ports_to_check:
        port = AD_PORTS.get(service)
        if port is None or port in checked_ports:
            continue
        checked_ports.add(port)
        results.append(check_port(host, port, service))

    if not skip_ldap_probe:
        results.append(check_ldap_banner(host))

    # Attempt reverse DNS for the resolved IPs
    try:
        addrs = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        seen_ips: set[str] = set()
        for addr in addrs:
            ip = addr[4][0]
            if ip not in seen_ips:
                seen_ips.add(ip)
                results.append(check_reverse_dns(ip))
    except socket.gaierror:
        pass

    return results


def build_report(
    domain: str,
    controllers: list[str],
    *,
    ports: Sequence[str] | None = None,
    skip_ldap_probe: bool = False,
) -> HealthReport:
    """Build a complete health report for an AD domain."""
    import datetime

    report = HealthReport(
        domain=domain,
        controllers=controllers,
        generated_at=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
    )
    for dc in controllers:
        report.results.extend(
            run_controller_checks(dc, check_ports_list=ports, skip_ldap_probe=skip_ldap_probe)
        )
    return report


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

STATUS_SYMBOL: dict[Status, str] = {
    Status.OK: "[OK]  ",
    Status.WARN: "[WARN]",
    Status.FAIL: "[FAIL]",
    Status.SKIP: "[SKIP]",
}


def format_report(report: HealthReport, *, verbose: bool = False) -> str:
    lines: list[str] = [
        f"AD Health Report — {report.domain}",
        f"Generated : {report.generated_at}",
        f"Controllers: {', '.join(report.controllers)}",
        "-" * 60,
    ]

    for result in report.results:
        symbol = STATUS_SYMBOL[result.status]
        timing = f"  ({result.elapsed_ms} ms)" if verbose and result.elapsed_ms else ""
        lines.append(f"{symbol}  {result.name:<28}  {result.target}{timing}")
        if verbose or result.status in (Status.FAIL, Status.WARN):
            lines.append(f"         {result.detail}")

    lines.append("-" * 60)
    summary = report.summary()
    overall = report.overall_status()
    lines.append(
        f"Summary: {summary['OK']} OK  {summary['WARN']} WARN  "
        f"{summary['FAIL']} FAIL  {summary['SKIP']} SKIP"
    )
    lines.append(f"Overall: {overall.value}")
    return "\n".join(lines)


def format_report_json(report: HealthReport) -> str:
    import json

    data = {
        "domain": report.domain,
        "controllers": report.controllers,
        "generated_at": report.generated_at,
        "overall": report.overall_status().value,
        "summary": report.summary(),
        "results": [
            {
                "name": r.name,
                "target": r.target,
                "status": r.status.value,
                "detail": r.detail,
                "elapsed_ms": r.elapsed_ms,
            }
            for r in report.results
        ],
    }
    return json.dumps(data, indent=2)
