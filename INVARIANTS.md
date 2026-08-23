# Invariants

## Conservation

For an accepted artifact, the gateway returns the exact artifact object and does not rewrite its governed state:
- identity
- payload
- provenance
- epistemic status
- authority
- scope
- integrity

## Construction boundary

The artifact model rejects unsupported value types and non-string mapping keys rather than silently coercing them. Nested JSON-like payload/provenance structures are frozen.

This matters because a silent coercion at construction would violate the same conservation principle the gateway is intended to enforce.

## Required governance state

The gateway rejects absent or invalid:
- provenance
- authority
- epistemic status
- scope
- integrity

Missing governance information never defaults to acceptance.

## Epistemic conservation

The gateway performs no epistemic promotion or downgrade.

In particular:
- INFERENCE does not become FACT
- RECOMMENDATION does not become DECISION
- ASSUMPTION does not become FACT
- UNKNOWN does not become FACT

Passing the gateway does not make content authoritative.

## Authority conservation

An object possessing a capability or being presented to the gateway does not thereby gain authority. V0.1 has no state-transition API and therefore rejects missing authority rather than manufacturing it.

## Scope conservation

The gateway does not broaden scope. V0.1 recognizes explicit `READ_ONLY` and `EXECUTE` scopes but performs no transitions between them.

## Integrity

A SHA-256 digest is calculated deterministically from the canonical representation of:
`artifact_id`, `payload`, `provenance`, `epistemic_status`, `authority`, and `scope`.

It detects modification of those fields after the digest was established, assuming the attacker cannot replace both the governed content and its expected digest.

It does **not** provide authentication, key management, non-repudiation, authorization, or protection against a fully compromised runtime.

The gateway additionally requires integrity to be exactly a 64-character lowercase hexadecimal SHA-256 representation.

## Failure rule

Unexpected, missing, malformed, or contradictory governance state must fail closed: `REJECT`, never silent `ACCEPT`.
