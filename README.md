# ad-health-checker

<!-- portfolio-card -->
<p align="center">
  <img src="docs/assets/project-card.svg" alt="ad-health-checker project card" width="100%" />
</p>
<!-- /portfolio-card -->

[![CI](https://github.com/LazyPanda902/ad-health-checker/actions/workflows/ci.yml/badge.svg)](https://github.com/LazyPanda902/ad-health-checker/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A Python-based Active Directory health monitoring and diagnostic tool for Windows system administrators. Probes domain controllers for DNS resolution, service port availability, Kerberos reachability, and LDAP connectivity to identify connectivity and configuration issues.

## Why this exists

This project focuses on common Active Directory connectivity checks that IT support teams perform during login, DNS, Kerberos, LDAP, and domain-controller troubleshooting. It uses only the Python standard library and keeps checks transparent for lab and learning use.

## Features

- **Comprehensive domain controller health checks** — DNS resolution, port availability, Kerberos KDC reachability, LDAP listener probes
- **Multiple check granularity** — Run full health reports or focus on specific checks (DNS, ports, Kerberos, LDAP)
- **Flexible service selection** — Choose which AD services to check: Kerberos, LDAP, LDAPS, SMB, DNS, RPC, Global Catalog variants
- **Dual output formats** — Plain-text reports with summary statistics or machine-readable JSON
- **Verbose reporting** — Optional timing information for each check to identify slow responses
- **Reverse DNS validation** — Verify PTR records for resolved IP addresses
- **Python 3.11+** — Uses only the Python standard library (no external dependencies)



## Privacy and security

This tool performs network and directory-connectivity checks against domain-controller hostnames supplied by the user. Do not publish real internal domain names, controller hostnames, IP addresses, or troubleshooting output from private environments.

Use sanitized lab values in screenshots, examples, issues, and public documentation.
## Installation

```bash
pip install -e .
```

Or from source:

```bash
git clone https://github.com/LazyPanda902/ad-health-checker.git
cd ad-health-checker
pip install .
```

## Usage

### Full Health Report

Run all checks against one or more domain controllers:

```bash
ad-health report --domain corp.example.com --controllers dc1.corp.example.com,dc2.corp.example.com
```

Example output:
```
AD Health Report — corp.example.com
Generated : 2026-06-15T14:30:00+00:00
Controllers: dc1.corp.example.com, dc2.corp.example.com
------------------------------------------------------------
[OK]   dns_resolution               dc1.corp.example.com
[OK]   port_kerberos                dc1:88
[OK]   port_ldap                    dc1:389
[WARN] port_ldaps                   dc1:636
       LDAPS port 636 unreachable: timed out
[OK]   ldap_banner                  dc1:389
[OK]   reverse_dns                  10.0.1.50
...
------------------------------------------------------------
Summary: 10 OK  2 WARN  0 FAIL  0 SKIP
Overall: WARN
```

With verbose timing:

```bash
ad-health report --domain corp.example.com --controllers dc1 --verbose
```

As JSON:

```bash
ad-health report --domain corp.example.com --controllers dc1 --json
```

### DNS Resolution Check

Test DNS resolution for one or more hostnames:

```bash
ad-health dns dc1.corp.example.com dc2.corp.example.com
```

Output:
```
[OK]   dc1.corp.example.com                         Resolved to: 10.0.1.50
[OK]   dc2.corp.example.com                         Resolved to: 10.0.1.51
```

### Port Availability Check

Probe AD service ports on domain controllers:

```bash
ad-health ports dc1.corp.example.com dc2.corp.example.com
```

Check specific services:

```bash
ad-health ports dc1 --services kerberos,ldap,smb
```

Available services: `kerberos` (88), `ldap` (389), `ldaps` (636), `smb` (445), `dns` (53), `ldap_gc` (3268), `ldaps_gc` (3269), `rpc_endpoint_mapper` (135)

Output:
```
[OK]   dc1:88                             kerberos port 88 is reachable
[OK]   dc1:389                            ldap port 389 is reachable
[FAIL] dc1:445                            smb port 445 unreachable: connection refused
```

### Kerberos KDC Reachability

Test Kerberos KDC availability (port 88 TCP):

```bash
ad-health kerberos dc1.corp.example.com dc2.corp.example.com
```

### LDAP Banner Probe

Send a minimal LDAP bind probe to verify the LDAP service is running:

```bash
ad-health ldap dc1.corp.example.com
```

## Testing

Run the test suite:

```bash
pip install -e ".[dev]"
pytest
```

Run tests with verbose output:

```bash
pytest -v
```

Run a specific test:

```bash
pytest tests/test_checker.py::test_check_dns_resolution_ok
```

## Exit Codes

- `0` — All checks passed (OK status)
- `1` — One or more checks failed (FAIL or WARN status)
- `2` — Invalid arguments or configuration error

## Requirements

- Python 3.11 or later
- Network connectivity to domain controllers
- For Kerberos checks: Kerberos client libraries (included in most Unix-like systems; Windows may require additional configuration)

## Limitations

- Probes use TCP connections; UDP-based checks (DNS queries, Kerberos auth-only) are not performed
- LDAP probe is an anonymous bind attempt; it does not validate user credentials or schema
- Does not modify any AD objects or configurations (read-only)
- Network timeouts default to 3 seconds per connection attempt

## License

MIT


## Repository owner

LazyPanda902 is Ali Bidhendi's GitHub username for this portfolio repository.
