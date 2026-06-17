"""Command-line interface for ad-health-checker."""

from __future__ import annotations

import argparse
import sys

from ad_health_checker.checker import (
    AD_PORTS,
    build_report,
    check_dns_resolution,
    check_kerberos_reachability,
    check_ldap_banner,
    format_report,
    format_report_json,
    run_controller_checks,
)


# ---------------------------------------------------------------------------
# Shared parent parser (avoids duplicate option definitions)
# ---------------------------------------------------------------------------

def _output_parent() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON instead of plain text",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Include timing and extra detail in plain-text output",
    )
    return p


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------

def _cmd_report(args: argparse.Namespace) -> int:
    controllers = [h.strip() for h in args.controllers.split(",") if h.strip()]
    if not controllers:
        print("Error: --controllers must list at least one hostname.", file=sys.stderr)
        return 2

    ports = [p.strip() for p in args.services.split(",") if p.strip()] if args.services else None
    report = build_report(
        args.domain,
        controllers,
        ports=ports,
        skip_ldap_probe=args.no_ldap_probe,
    )

    if args.json:
        print(format_report_json(report))
    else:
        print(format_report(report, verbose=args.verbose))

    return 0 if report.overall_status().value == "OK" else 1


def _cmd_dns(args: argparse.Namespace) -> int:
    results = [check_dns_resolution(h) for h in args.hosts]
    if args.json:
        import json
        data = [
            {"host": r.target, "status": r.status.value, "detail": r.detail, "elapsed_ms": r.elapsed_ms}
            for r in results
        ]
        print(json.dumps(data, indent=2))
    else:
        for r in results:
            print(f"[{r.status.value:<4}]  {r.target:<40}  {r.detail}")

    failed = sum(1 for r in results if r.status.value == "FAIL")
    return 1 if failed else 0


def _cmd_ports(args: argparse.Namespace) -> int:
    services = [s.strip() for s in args.services.split(",") if s.strip()] if args.services else list(AD_PORTS.keys())
    invalid = [s for s in services if s not in AD_PORTS]
    if invalid:
        known = ", ".join(sorted(AD_PORTS))
        print(f"Error: unknown service(s): {', '.join(invalid)}.  Known: {known}", file=sys.stderr)
        return 2

    results = []
    for host in args.hosts:
        for svc in services:
            from ad_health_checker.checker import check_port
            results.append(check_port(host, AD_PORTS[svc], svc))

    if args.json:
        import json
        data = [
            {"target": r.target, "service": r.name.removeprefix("port_"), "status": r.status.value, "detail": r.detail}
            for r in results
        ]
        print(json.dumps(data, indent=2))
    else:
        for r in results:
            print(f"[{r.status.value:<4}]  {r.target:<35}  {r.detail}")

    failed = sum(1 for r in results if r.status.value == "FAIL")
    return 1 if failed else 0


def _cmd_kerberos(args: argparse.Namespace) -> int:
    results = [check_kerberos_reachability(h) for h in args.hosts]
    if args.json:
        import json
        data = [
            {"host": r.target, "status": r.status.value, "detail": r.detail}
            for r in results
        ]
        print(json.dumps(data, indent=2))
    else:
        for r in results:
            print(f"[{r.status.value:<4}]  {r.target:<35}  {r.detail}")

    failed = sum(1 for r in results if r.status.value == "FAIL")
    return 1 if failed else 0


def _cmd_ldap(args: argparse.Namespace) -> int:
    results = [check_ldap_banner(h) for h in args.hosts]
    if args.json:
        import json
        data = [
            {"host": r.target, "status": r.status.value, "detail": r.detail}
            for r in results
        ]
        print(json.dumps(data, indent=2))
    else:
        for r in results:
            print(f"[{r.status.value:<4}]  {r.target:<35}  {r.detail}")

    failed = sum(1 for r in results if r.status.value == "FAIL")
    return 1 if failed else 0


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    out = _output_parent()

    root = argparse.ArgumentParser(
        prog="ad-health",
        description="Active Directory health checker — network and service probes",
    )
    root.add_argument("--version", action="version", version="ad-health-checker 0.1.0")

    sub = root.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # --- report -----------------------------------------------------------
    p_report = sub.add_parser(
        "report",
        parents=[out],
        help="Run all health checks and produce a full report",
    )
    p_report.add_argument("--domain", required=True, metavar="DOMAIN",
                          help="AD domain name (e.g. corp.example.com)")
    p_report.add_argument("--controllers", required=True, metavar="HOST[,HOST...]",
                          help="Comma-separated list of domain controller hostnames/IPs")
    p_report.add_argument("--services", "--ports", dest="services", default=None, metavar="SVC[,SVC...]",
                          help=f"Comma-separated service names to check. Known: {', '.join(AD_PORTS)}")
    p_report.add_argument("--no-ldap-probe", action="store_true", default=False,
                          help="Skip the LDAP banner probe")
    p_report.set_defaults(func=_cmd_report)

    # --- dns --------------------------------------------------------------
    p_dns = sub.add_parser(
        "dns",
        parents=[out],
        help="Resolve one or more hostnames and report DNS health",
    )
    p_dns.add_argument("hosts", nargs="+", metavar="HOST",
                       help="Hostnames to resolve")
    p_dns.set_defaults(func=_cmd_dns)

    # --- ports ------------------------------------------------------------
    p_ports = sub.add_parser(
        "ports",
        parents=[out],
        help="Check AD service ports on one or more hosts",
    )
    p_ports.add_argument("hosts", nargs="+", metavar="HOST",
                         help="Hostnames or IPs to probe")
    p_ports.add_argument("--services", default=None, metavar="SVC[,SVC...]",
                         help=f"Comma-separated services. Known: {', '.join(AD_PORTS)}")
    p_ports.set_defaults(func=_cmd_ports)

    # --- kerberos ---------------------------------------------------------
    p_krb = sub.add_parser(
        "kerberos",
        parents=[out],
        help="Check Kerberos KDC reachability (TCP/88)",
    )
    p_krb.add_argument("hosts", nargs="+", metavar="HOST",
                       help="Domain controller hostnames or IPs")
    p_krb.set_defaults(func=_cmd_kerberos)

    # --- ldap -------------------------------------------------------------
    p_ldap = sub.add_parser(
        "ldap",
        parents=[out],
        help="Send a minimal LDAP bind probe to verify the LDAP listener",
    )
    p_ldap.add_argument("hosts", nargs="+", metavar="HOST",
                        help="Domain controller hostnames or IPs")
    p_ldap.set_defaults(func=_cmd_ldap)

    return root


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
