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
- Expiry and revocation are not implemented in this package. There is no expiry field on `Authority` and no revocation list or registry. Any revocation delay is bounded by the lifetime of the grant as the caller's verifier enforces it.
- Issuer identity, key management and signature verification are not implemented. The package has no keys. `Authority.grant` is an opaque string checked only for presence.
- Replay protection and action binding are not implemented.
- Declared scope is validated and preserved, not enforced.
- The gateway cannot force a caller to honour a refusal. Downstream enforcement is the caller's responsibility.
- No protection against a compromised runtime. Code in the same Python process can change any object the gateway uses.

Reports about these limits are welcome. They are most useful when they show a concrete case where a limit is worse than documented.

## Deployment requirements

The gateway is a library. It returns a decision and cannot force anything. A production deployment that relies on it needs all of the following, provided by the deployer:

- The `PRODUCTION` profile, so the gateway refuses to run without a verifier.
- A trusted `authority_verifier`. The package does not supply one, and `PRODUCTION` only checks that a callable exists, not that it is trustworthy.
- Downstream enforcement of every refusal. A caller that ignores a `GateResult` is outside what the gateway can prevent.
- Producer authentication, handled by separate controls. The digest does not provide it.
- Logging and monitoring of refusals. The package keeps no durable log.

## Verifier trust boundary and outages

- The verifier is supplied by the caller and is trusted by the gateway. The gateway does not check the verifier's identity, code, or correctness.
- `PRODUCTION` checks only that a callable exists. It does not establish that the callable is trustworthy.
- A verifier that raises, or returns anything other than literal `True` or `False`, refuses the artifact with `AUTHORITY_VERIFIER_UNAVAILABLE`. A verifier that returns literal `False` refuses with `MISSING_AUTHORITY`. Neither outcome accepts.
- Exception text from the verifier is kept out of the public verdict, because it may contain secrets. Nothing in this package logs it.
- Outages therefore appear as refusals. An operator must watch for `AUTHORITY_VERIFIER_UNAVAILABLE` to see them.

Meeting these requirements does not make the package an authorization system. It remains an admission check.

## Supported versions

Only the `main` branch receives fixes. The package is at version `0.1.0`.
