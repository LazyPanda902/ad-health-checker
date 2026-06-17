# Testing Guide

## Running Tests

### Prerequisites

Install the project with development dependencies:

```bash
pip install -e ".[dev]"
```

This installs `pytest` and the `ad-health-checker` package in development mode.

### Run All Tests

```bash
pytest
```

Example output:
```
tests/test_checker.py::test_status_values PASSED
tests/test_checker.py::test_status_is_str PASSED
tests/test_checker.py::test_ad_ports_has_expected_services PASSED
tests/test_checker.py::test_kerberos_port PASSED
...
tests/test_checker.py::test_main_dns_fail_exits_nonzero PASSED
======================== 50 passed in 0.45s =========================
```

### Run Tests with Verbose Output

```bash
pytest -v
```

Shows the name of each test as it runs.

### Run Tests with Coverage Report

```bash
pip install pytest-cov
pytest --cov=ad_health_checker --cov-report=html
```

Opens an HTML coverage report in `htmlcov/index.html`.

### Run a Specific Test

```bash
pytest tests/test_checker.py::test_check_dns_resolution_ok
```

### Run Tests Matching a Pattern

```bash
pytest -k "dns" -v
```

Runs all tests with "dns" in their name.

## Test Coverage

The test suite covers:

### Core Functionality Tests

- **Status enum** — Validation of status values and string representation
- **AD ports constant** — Verification of all known AD service ports (Kerberos, LDAP, SMB, DNS, RPC, Global Catalog variants)
- **CheckResult dataclass** — Field initialization and defaults
- **HealthReport dataclass** — Summary calculation, overall status logic

### Individual Check Tests

- **DNS resolution** — Success, failure, and timing for `check_dns_resolution()`
- **Port connectivity** — Success, connection refused, timeout scenarios for `check_port()`
- **Reverse DNS** — PTR record lookup success and failures
- **LDAP banner probe** — Valid response, empty response, connection failure scenarios
- **Kerberos reachability** — Delegation to port check for port 88
- **Controller orchestration** — Multi-check sequencing, DNS failure cascade, LDAP probe skipping

### Report Building and Formatting Tests

- **Report structure** — Domain, controller list, timestamp, results collection
- **Multi-controller handling** — Checks run for each controller
- **Text formatting** — Plain-text report with summary and overall status
- **JSON formatting** — Valid JSON structure with all required fields
- **Verbose output** — Timing information included when requested
- **Failure detail display** — FAIL/WARN status details shown in plain-text output

### Command-Line Interface Tests

- **Parser construction** — Argparse parser builds without errors
- **Subcommands** — All five subcommands (report, dns, ports, kerberos, ldap) parse correctly
- **Report arguments** — Domain, controller list parsing with CSV support
- **Port selection** — Service name parsing and validation
- **Flags** — JSON output, verbose, no-ldap-probe flags work correctly
- **Error handling** — Missing required arguments, unknown services, invalid options exit with code 2
- **Exit codes** — Success (0), failure (1), argument errors (2)

### Integration Tests

- **End-to-end workflow** — Full health report generation from CLI args to formatted output
- **Mock network calls** — All I/O operations are mocked; tests do not require network access

## Test Structure

Tests use `unittest.mock` to avoid network calls:

```python
# Example: Test DNS success without network
def test_check_dns_resolution_ok():
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [(None, None, None, None, ("127.0.0.1", 0))]
        result = check_dns_resolution("localhost")
    assert result.status == Status.OK
    assert "127.0.0.1" in result.detail
```

All socket operations are patched:
- `socket.getaddrinfo()` — DNS resolution
- `socket.gethostbyaddr()` — Reverse DNS
- `socket.create_connection()` — Port connectivity

## Running Tests in CI/CD

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: pip install -e ".[dev]"
    - name: Run tests
      run: pytest -v
```

### Local CI Simulation

Run the same tests that CI will run:

```bash
# Install in development mode with test dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Check exit code
echo "Test result: $?"
```

## Test Isolation

Each test is isolated:

- No persistent state between tests
- All I/O is mocked
- No temporary files created
- No network calls made

Tests can be run in any order and in parallel:

```bash
pytest -n auto  # Requires pytest-xdist
```

## Debugging Tests

### Run a single test with verbose output

```bash
pytest -vv tests/test_checker.py::test_check_dns_resolution_ok
```

### Print debug information

Add `print()` statements or use `pytest.set_trace()`:

```python
def test_example():
    result = some_function()
    pytest.set_trace()  # Drops into pdb debugger
    assert result == expected
```

Run with:

```bash
pytest -vv -s tests/test_checker.py::test_example
```

The `-s` flag shows print output.

### Inspect mock calls

```python
def test_mock_inspection():
    with patch("socket.getaddrinfo") as mock:
        check_dns_resolution("test")
    
    # Verify how the mock was called
    mock.assert_called_once_with("test", None, proto=socket.IPPROTO_TCP)
    print(f"Call args: {mock.call_args}")
```

## Adding New Tests

### Test naming convention

- Test file: `tests/test_*.py`
- Test function: `def test_<feature>_<scenario>():`
- Examples: `test_check_port_timeout`, `test_format_report_verbose_includes_timing`

### Test template

```python
def test_new_feature():
    """One-line description of what this test verifies."""
    with patch("module.function") as mock_func:
        mock_func.return_value = expected_value
        
        result = code_under_test()
        
        assert result == expected
        mock_func.assert_called_once()
```

### Running your new test

```bash
pytest tests/test_checker.py::test_new_feature -v
```

## Known Limitations

- Tests do not perform actual network calls; they mock all socket operations
- Tests do not validate timing accuracy; elapsed_ms is mocked
- Tests do not exercise Windows-specific behavior (though the code is cross-platform)
- LDAP probe tests do not validate BER encoding, only mock responses

## Continuous Integration

The test suite is designed to:
- Run on any Python 3.11+ interpreter
- Require no external services or network access
- Complete in < 1 second on modern hardware
- Produce consistent, reproducible results
