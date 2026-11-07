# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's security advisories:

https://github.com/wking53214/Governance_Gateway/security/advisories/new

Do not open a public issue for a suspected vulnerability. The maintainer will acknowledge the report and work with you on a fix before any public disclosure.

## What this package is and is not

Governance_Gateway judges whether an artifact is well-formed, unchanged since its digest was computed, and carries the fields it claims. It is an admission check, not an authorization system. Read `README.md` and `ARCHITECTURE.md` (trust model) before relying on it for a security decision.

Known limits, stated in the docs and not treated as vulnerabilities by themselves:

- The integrity digest is unkeyed SHA-256. It detects accidental or unauthorized edits that do not also replace the digest. It does not authenticate the producer.
- In the default `DEVELOPMENT` profile, no authority verifier is required, so any well-formed authority record passes.
- Frozen objects are an API guarantee. They do not protect against code running in the same Python process.

Reports about these limits are welcome. They are most useful when they show a concrete case where a limit is worse than documented.

## Supported versions

Only the `main` branch receives fixes. The package is at version `0.1.0`.
