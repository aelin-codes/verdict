# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Yes    |

---

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues by emailing **security@verdict-dev.io** (or open a [GitHub private security advisory](https://github.com/verdict-dev/verdict/security/advisories/new)).

Include as much of the following as possible:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

You can expect an acknowledgement within **48 hours** and a status update within **7 days**.

---

## Scope

Verdict runs `git diff` via subprocess and imports/executes code via `sys.settrace`. Known security considerations:

- `repo_path` passed to the HTTP API or CLI is **not sandboxed** — only point Verdict at repos you trust.
- The `run_tests` flag executes the repo's test suite; do not enable it against untrusted repositories.
- The MCP server reads from stdin and writes to stdout — it does not open any network sockets itself.
