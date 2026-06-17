# Usage Examples

## Example 1: Full Health Report for a Single Controller

Check one domain controller with all available diagnostics:

```bash
$ ad-health report --domain corp.example.com --controllers dc1.corp.example.com
```

Output:
```
AD Health Report — corp.example.com
Generated : 2026-06-15T14:30:45.123456+00:00
Controllers: dc1.corp.example.com
------------------------------------------------------------
[OK]   dns_resolution               dc1.corp.example.com
[OK]   port_kerberos                dc1.corp.example.com:88
[OK]   port_ldap                    dc1.corp.example.com:389
[OK]   port_smb                     dc1.corp.example.com:445
[OK]   port_ldap_gc                 dc1.corp.example.com:3268
[OK]   port_ldaps_gc                dc1.corp.example.com:3269
[OK]   port_dns                     dc1.corp.example.com:53
[OK]   port_rpc_endpoint_mapper     dc1.corp.example.com:135
[OK]   ldap_banner                  dc1.corp.example.com:389
[OK]   reverse_dns                  10.0.1.50
------------------------------------------------------------
Summary: 10 OK  0 WARN  0 FAIL  0 SKIP
Overall: OK
```

## Example 2: Multiple Domain Controllers with Verbose Output

Check two domain controllers and include timing information:

```bash
$ ad-health report --domain corp.local --controllers dc1.corp.local,dc2.corp.local --verbose
```

Output:
```
AD Health Report — corp.local
Generated : 2026-06-15T14:35:12.456789+00:00
Controllers: dc1.corp.local, dc2.corp.local
------------------------------------------------------------
[OK]   dns_resolution               dc1.corp.local  (2.34 ms)
[OK]   port_kerberos                dc1:88  (15.67 ms)
[OK]   port_ldap                    dc1:389  (18.45 ms)
[WARN] port_ldaps                   dc1:636  (3001.23 ms)
       LDAPS port 636 unreachable: timed out
[OK]   ldap_banner                  dc1:389  (25.12 ms)
[OK]   reverse_dns                  10.0.1.50  (5.67 ms)
[OK]   dns_resolution               dc2.corp.local  (1.89 ms)
[OK]   port_kerberos                dc2:88  (14.23 ms)
[OK]   port_ldap                    dc2:389  (19.34 ms)
[OK]   port_ldaps                   dc2:636  (22.45 ms)
[OK]   ldap_banner                  dc2:389  (26.78 ms)
[OK]   reverse_dns                  10.0.1.51  (4.56 ms)
------------------------------------------------------------
Summary: 11 OK  1 WARN  0 FAIL  0 SKIP
Overall: WARN
```

## Example 3: JSON Output for Machine Parsing

Get structured output for integration with monitoring systems:

```bash
$ ad-health report --domain corp.local --controllers dc1 --json
```

Output:
```json
{
  "domain": "corp.local",
  "controllers": ["dc1"],
  "generated_at": "2026-06-15T14:40:00.000000+00:00",
  "overall": "OK",
  "summary": {
    "OK": 9,
    "WARN": 0,
    "FAIL": 0,
    "SKIP": 0
  },
  "results": [
    {
      "name": "dns_resolution",
      "target": "dc1",
      "status": "OK",
      "detail": "Resolved to: 10.0.1.50",
      "elapsed_ms": 2.34
    },
    {
      "name": "port_kerberos",
      "target": "dc1:88",
      "status": "OK",
      "detail": "kerberos port 88 is reachable",
      "elapsed_ms": 15.67
    },
    {
      "name": "port_ldap",
      "target": "dc1:389",
      "status": "OK",
      "detail": "ldap port 389 is reachable",
      "elapsed_ms": 18.45
    }
  ]
}
```

## Example 4: Check Specific Services Only

Check only Kerberos and LDAP on a controller (skip other services):

```bash
$ ad-health report --domain corp.local --controllers dc1 --services kerberos,ldap
```

Skip the LDAP banner probe:

```bash
$ ad-health report --domain corp.local --controllers dc1 --no-ldap-probe
```

## Example 5: DNS Resolution Check

Resolve multiple hostnames:

```bash
$ ad-health dns dc1.corp.local dc2.corp.local dc3.corp.local
```

Output:
```
[OK]   dc1.corp.local                              Resolved to: 10.0.1.50
[OK]   dc2.corp.local                              Resolved to: 10.0.1.51
[FAIL] dc3.corp.local                              DNS lookup failed: Name or service not known
```

## Example 6: Port Availability Check

Check all default AD ports on a single host:

```bash
$ ad-health ports dc1.corp.local
```

Output:
```
[OK]   dc1:88                             kerberos port 88 is reachable
[OK]   dc1:389                            ldap port 389 is reachable
[OK]   dc1:445                            smb port 445 is reachable
[OK]   dc1:3268                           ldap_gc port 3268 is reachable
[OK]   dc1:3269                           ldaps_gc port 3269 is reachable
[OK]   dc1:53                             dns port 53 is reachable
[OK]   dc1:135                            rpc_endpoint_mapper port 135 is reachable
[OK]   dc1:636                            ldaps port 636 is reachable
```

Check specific services on multiple hosts:

```bash
$ ad-health ports dc1 dc2 dc3 --services kerberos,ldap,smb
```

## Example 7: Kerberos KDC Reachability

Test KDC availability:

```bash
$ ad-health kerberos dc1.corp.local dc2.corp.local
```

Output:
```
[OK]   dc1.corp.local                     kerberos port 88 is reachable
[OK]   dc2.corp.local                     kerberos port 88 is reachable
```

## Example 8: LDAP Banner Probe

Verify LDAP service is responding:

```bash
$ ad-health ldap dc1.corp.local
```

Output:
```
[OK]   dc1.corp.local:389                 LDAP listener responded (14 bytes)
```

## Example 9: Detecting Connection Issues

Check controllers when some are unreachable:

```bash
$ ad-health report --domain corp.local --controllers dc1,dc2-unavailable --json
```

Output shows DNS failures cause port checks to be skipped:
```json
{
  "overall": "FAIL",
  "results": [
    {
      "name": "dns_resolution",
      "target": "dc1",
      "status": "OK",
      "detail": "Resolved to: 10.0.1.50",
      "elapsed_ms": 2.45
    },
    {
      "name": "dns_resolution",
      "target": "dc2-unavailable",
      "status": "FAIL",
      "detail": "DNS lookup failed: Name or service not known",
      "elapsed_ms": 1.23
    },
    {
      "name": "port_checks_skipped",
      "target": "dc2-unavailable",
      "status": "SKIP",
      "detail": "Skipped port checks because DNS resolution failed",
      "elapsed_ms": 0.0
    }
  ]
}
```

## Exit Code Patterns

Use exit codes in scripts to detect health status:

```bash
$ ad-health dns dc1.corp.local
$ echo "Exit code: $?"
Exit code: 0  # Success — DNS resolved

$ ad-health dns invalid.nonexistent.local
$ echo "Exit code: $?"
Exit code: 1  # Failure — DNS did not resolve

$ ad-health report --domain corp.local --controllers
# Missing required argument
$ echo "Exit code: $?"
Exit code: 2  # Invalid arguments
```

## Notes before publishing

- Examples use placeholder domains such as corp.example.com.
- Commands are intended for local lab or authorized admin networks only.
- Source installation uses pip install -e . until the package is published.
