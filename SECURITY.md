# Security Policy

## Overview

ad-health-checker is a diagnostic tool designed to assist system administrators in monitoring Active Directory infrastructure health. It performs network connectivity and service availability checks only — it does not modify AD configurations or authenticate with credentials.

## What This Tool Does

- Performs TCP port probes to check service availability
- Sends minimal LDAP anonymous bind requests to verify LDAP listeners
- Performs DNS resolution and reverse DNS lookups
- Outputs diagnostics in plain text or JSON format

## What This Tool Does NOT Do

- Does not store, cache, or transmit credentials or authentication tokens
- Does not modify any Active Directory objects, attributes, or configurations
- Does not perform user authentication or credential validation
- Does not perform Kerberos authentication; only checks KDC port availability
- Does not query LDAP schema or directory contents (anonymous bind only)

## Security Considerations

### Network Access

Ensure the system running ad-health-checker has appropriate network access to domain controllers. The tool initiates outbound TCP connections to the following ports by default:

- 88 (Kerberos KDC)
- 389 (LDAP)
- 636 (LDAPS)
- 445 (SMB)
- 53 (DNS)
- 135 (RPC Endpoint Mapper)
- 3268/3269 (Global Catalog)

### Output Security

**DO NOT commit or publish:**

- Output files containing real domain names, controller hostnames, or IP addresses
- Network topology information derived from successful probe results
- Domain structure information from successful LDAP probes
- Any configuration files specifying real domain controller addresses

When sharing diagnostic output for troubleshooting:
- Sanitize hostnames and IP addresses
- Use example domains (e.g., `corp.example.com`) in documentation or test cases
- Do not include output files in version control

### Credentials and Secrets

This tool does not use or require credentials. Do not:

- Attempt to modify the tool to store or cache passwords
- Pass credentials as command-line arguments
- Configure credentials in environment variables for this tool's use

## Reporting Security Issues

If you discover a security vulnerability in ad-health-checker, please report it responsibly:

1. Do not publicly disclose the vulnerability until a fix is available
2. Contact the maintainer with details of the issue
3. Allow reasonable time for a fix before public disclosure

## Dependencies

This tool uses only Python's standard library (`socket`, `argparse`, `json`, `dataclasses`, `datetime`) to minimize the attack surface and eliminate dependency vulnerabilities.

## Compliance Notes

- The tool is read-only with respect to Active Directory — it cannot be used to exfiltrate data or modify configurations
- No logs, credentials, or sensitive data are stored or cached by the tool itself
- Output should be treated as potentially sensitive infrastructure information and handled appropriately within your organization
