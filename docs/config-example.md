# Configuration and Environment Setup

## Command-Line Configuration

ad-health-checker uses command-line arguments to specify domain, controllers, and check options. There are no configuration files to maintain.

## Typical Setup Scenarios

### Scenario 1: Single Site with Two Domain Controllers

For a single-site Active Directory environment with two domain controllers:

```bash
ad-health report \
  --domain corp.example.com \
  --controllers dc1.corp.example.com,dc2.corp.example.com
```

### Scenario 2: Multi-Site Setup with Site-Specific Checks

Check domain controllers in multiple sites separately to identify site-level issues:

```bash
# Check site A
ad-health report \
  --domain corp.example.com \
  --controllers dc1-siteA.corp.example.com,dc2-siteA.corp.example.com

# Check site B
ad-health report \
  --domain corp.example.com \
  --controllers dc1-siteB.corp.example.com,dc2-siteB.corp.example.com
```

### Scenario 3: Network Segmentation Testing

Check only essential services across a firewall boundary:

```bash
ad-health report \
  --domain corp.example.com \
  --controllers dc1.dmz.example.com \
  --services kerberos,ldap,smb \
  --no-ldap-probe
```

## Environment Variables

This tool does not use environment variables for configuration. All settings are passed via command-line arguments.

If you need to store frequently used controller addresses, use shell aliases or scripts:

```bash
# In ~/.bashrc or ~/.zshrc
alias check-corp-ad='ad-health report --domain corp.example.com --controllers dc1.corp.example.com,dc2.corp.example.com'
```

Then use:

```bash
check-corp-ad
check-corp-ad --verbose
check-corp-ad --json
```

## Integration with Monitoring Scripts

### Example: Bash wrapper for monitoring

```bash
#!/bin/bash
set -e

DOMAIN="corp.example.com"
CONTROLLERS="dc1.corp.example.com,dc2.corp.example.com"
OUTPUT_DIR="/var/log/ad-health"

timestamp=$(date +%Y%m%d-%H%M%S)
report_file="$OUTPUT_DIR/report-$timestamp.json"

ad-health report \
  --domain "$DOMAIN" \
  --controllers "$CONTROLLERS" \
  --json > "$report_file"

# Extract overall status and alert if needed
overall=$(jq -r '.overall' "$report_file")

if [ "$overall" = "FAIL" ]; then
  echo "AD Health Check FAILED" | mail -s "AD Health Alert" admin@corp.example.com
  exit 1
elif [ "$overall" = "WARN" ]; then
  echo "AD Health Check WARNING" >> /var/log/ad-health/warnings.log
  exit 0
else
  exit 0
fi
```

### Example: Python monitoring integration

```python
#!/usr/bin/env python3
import subprocess
import json
import sys

def check_ad_health(domain, controllers):
    cmd = [
        "ad-health", "report",
        "--domain", domain,
        "--controllers", ",".join(controllers),
        "--json"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0 and result.stdout:
        report = json.loads(result.stdout)
        return report
    else:
        print(f"Error running ad-health: {result.stderr}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    report = check_ad_health(
        "corp.example.com",
        ["dc1.corp.example.com", "dc2.corp.example.com"]
    )
    
    # Send to monitoring system (Prometheus, Datadog, etc.)
    print(f"Overall Status: {report['overall']}")
    print(f"Summary: {report['summary']}")
    
    # Parse results for alerting logic
    failures = [r for r in report['results'] if r['status'] == 'FAIL']
    if failures:
        print(f"Failed checks: {len(failures)}")
        for f in failures:
            print(f"  - {f['name']}: {f['detail']}")
```

## Network Requirements

Ensure the host running ad-health-checker has outbound TCP access to domain controllers on these ports:

| Service | Port | Required | Notes |
|---------|------|----------|-------|
| Kerberos | 88 | Yes | KDC availability |
| LDAP | 389 | Yes | Directory service |
| LDAPS | 636 | No | Encrypted LDAP (optional check) |
| SMB | 445 | Yes | File sharing and RPC |
| DNS | 53 | Yes | Domain name resolution |
| RPC Endpoint Mapper | 135 | Yes | RPC service discovery |
| Global Catalog | 3268/3269 | Optional | Forest-wide queries |

### Firewall Configuration Example

```bash
# Allow outbound connections to domain controllers (iptables example)
iptables -A OUTPUT -d 10.0.1.0/24 -p tcp -m multiport --dports 53,88,135,389,445,636,3268,3269 -j ACCEPT
```

## Time Synchronization

Domain controllers and the monitoring host should have synchronized clocks (within ~5 minutes recommended) for reliable Kerberos health assessment. If clock skew is excessive:

- Kerberos port (88) may appear unreachable
- LDAP connections may fail silently
- Reverse DNS lookups may timeout

Ensure NTP or similar time synchronization is configured on all systems.

## DNS Configuration

The monitoring host should use DNS servers that can resolve the domain controller hostnames. If using split-view DNS:

- Ensure the monitoring host queries the correct DNS zone (internal AD DNS, not external)
- Verify that A and PTR records are configured correctly for all domain controllers

Example DNS check before running ad-health-checker:

```bash
nslookup dc1.corp.example.com  # Verify forward resolution
nslookup 10.0.1.50             # Verify reverse DNS (PTR)
```

## Logging and Output Capture

### Save reports to file

```bash
ad-health report --domain corp.example.com --controllers dc1 --json > health-report.json
ad-health report --domain corp.example.com --controllers dc1 --verbose > health-report.txt
```

### Pipe to other tools

```bash
# Pretty-print JSON
ad-health report --domain corp.example.com --controllers dc1 --json | jq '.'

# Extract specific fields
ad-health report --domain corp.example.com --controllers dc1 --json | jq '.summary'

# Count failures
ad-health report --domain corp.example.com --controllers dc1 --json | jq '[.results[] | select(.status=="FAIL")] | length'
```

## Performance Tuning

Default TCP connection timeout is 3 seconds per port. This is appropriate for local networks. For high-latency networks or WAN connections, monitor `elapsed_ms` in verbose output:

```bash
ad-health report --domain corp.example.com --controllers dc1 --verbose
```

If timeouts occur frequently, verify:
- Network connectivity to domain controllers
- Firewall rules allowing bidirectional traffic
- Network latency (run `ping` and `traceroute` diagnostics)

## DNS troubleshooting notes

If DNS checks fail, verify that the client machine is using domain DNS servers and that each controller hostname resolves from the same network where the check runs.

Useful checks before running the tool:

- nslookup dc1.corp.example.com
- nslookup corp.example.com

For segmented networks, run `ad-health report --services kerberos,ldap,smb` from each network zone to confirm which services are reachable.

## Notes before publishing

- Examples use placeholder domains such as corp.example.com.
- Commands are intended for local lab or authorized admin networks only.
- Source installation uses pip install -e . until the package is published.
