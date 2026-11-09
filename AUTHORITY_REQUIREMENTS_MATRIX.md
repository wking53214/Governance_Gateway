# Authority requirements matrix

Source of requirements: docs/AUTHORITY_CONTRACT.md. "Result" is from a local test run, not GitHub CI: 465 passed (CNS present), 274 passed and 1 skipped (CNS absent). "Implemented?" uses the labels IMPLEMENTED, PARTIAL, NOT IMPLEMENTED, DECIDED.

| Requirement | Implemented? | Source | Test | Result | Deferred dependency |
|---|---|---|---|---|---|
| R1 Trusted issuer identity pinned by operator | NOT IMPLEMENTED | none | none | n/a | Operator key file; decision A |
| R2 Grant signature verified against issuer | NOT IMPLEMENTED | none (`Authority.grant` is opaque text) | none | n/a | Key management and signing scheme; out of scope |
| R3 Expiry enforced | NOT IMPLEMENTED in package (verifier's job) | none (no expiry field) | none | n/a | Expiry in grant and verifier |
| R4 Revocation at decision time | NOT IMPLEMENTED; contract is bounded revocation (decision B) | none | none | n/a | Revocation mechanism, not built |
| R5 Grant covers this actor | PARTIAL: caller-supplied verifier receives actor | `gateway.py` verifier call | `test_with_a_verifier_an_unverified_grant_is_refused_as_missing_authority`; `test_with_a_verifier_a_registered_grant_is_accepted` | PASS | Verifier must check actor |
| R6 Grant covers this action | NOT IMPLEMENTED | none (no action in Artifact) | none | n/a | Action model; verifier request (R14) |
| R7 Grant covers artifact scope | NOT IMPLEMENTED | none | none | n/a | Verifier request (R14) |
| R8 Replay protection | NOT IMPLEMENTED | none | none | n/a | Nonce store |
| R9 Verifier unavailable refuses | IMPLEMENTED | `gateway.py` except branch | `test_a_verifier_that_raises_refuses_the_artifact_as_unavailable` | PASS | none |
| R10 Verifier exception does not prove grant invalid | IMPLEMENTED | `models.py` reason; `gateway.py` | `test_a_verifier_outage_does_not_leak_its_exception_into_the_verdict`; `test_a_verifier_that_answers_false_is_a_refusal_not_an_outage` | PASS | none |
| R11 Malformed verifier response refuses | IMPLEMENTED (as AUTHORITY_VERIFIER_UNAVAILABLE) | `gateway.py` else branch | `test_a_malformed_answer_is_a_verifier_failure_not_a_verdict_on_the_grant` (6 cases) | PASS | none |
| R12 Tampered artifact never reaches verifier | IMPLEMENTED | `gateway.py` order | `test_verifier_is_not_called_for_an_artifact_with_a_bad_digest` | PASS | none |
| R13 PRODUCTION refuses without verifier | IMPLEMENTED (existence check only) | `gateway.py` `__init__`, `_judge` | `test_production_without_a_verifier_refuses_to_be_built`; `..._non_callable_...` | PASS | Trust of verifier is caller's |
| R14 Verifier request object with artifact context | NOT IMPLEMENTED; public API change, owner decision | none | none | n/a | Owner decision before any change |
| Verifier signature `authority_verifier(Authority) -> bool` | IMPLEMENTED | `gateway.py` | `test_with_no_verifier_any_authority_is_accepted` and related | PASS | none |
| Verifier returns literal False | IMPLEMENTED | `gateway.py` | `test_an_explicit_false_is_a_refusal_of_the_grant` | PASS | none |
| Verifier returns None | IMPLEMENTED (malformed, AUTHORITY_VERIFIER_UNAVAILABLE) | `gateway.py` | malformed test, `None` case | PASS | none |
| Verifier returns non-boolean value | IMPLEMENTED (malformed, AUTHORITY_VERIFIER_UNAVAILABLE) | `gateway.py` | malformed test, `0`, `1`, `"yes"`, `[True]`, `1.0` cases | PASS | none |
| Verifier raises | IMPLEMENTED | `gateway.py` | as R9 | PASS | none |
| Development profile behaves as documented | IMPLEMENTED | `gateway.py` | `test_default_profile_is_development_and_keeps_the_original_behaviour` | PASS | none |
| Production profile behaves as documented | IMPLEMENTED | `gateway.py` | `test_production_refuses_a_resealed_edit_from_an_unverified_actor`; `test_production_accepts_a_verified_actor` | PASS | none |
| Malformed verification request | NOT APPLICABLE: request is an Authority, validated at construction | `models.py` | `test_gateway_does_not_create_authority`; authority construction in `test_gateway.py` | PASS | none |
| Unknown issuer rejected | NOT IMPLEMENTED | none | none | n/a | R1 |
| Invalid signature rejected | NOT IMPLEMENTED | none | none | n/a | R2 |
| Expired grant rejected | NOT IMPLEMENTED in package | none | none | n/a | R3 |
| Wrong actor rejected | PARTIAL (via caller verifier) | as R5 | as R5 | PASS | Caller verifier |
| Wrong scope rejected | NOT IMPLEMENTED | none | none | n/a | R7 |
| Wrong action rejected | NOT IMPLEMENTED | none | none | n/a | R6 |
| Replay refused | NOT IMPLEMENTED | none | none | n/a | R8 |
| Dashboard failure does not change verdict (accepted and rejected) | IMPLEMENTED | `gateway.py` `evaluate` | `test_a_failing_dashboard_keeps_an_accepted_verdict_and_logs_it`; `test_a_failing_dashboard_keeps_a_rejected_verdict_and_logs_it` | PASS | none |

## Summary

- IMPLEMENTED with tests: R5 (caller-supplied, partial), R9, R10, R11, R12, R13 (existence only), the verifier signature, the False and malformed mappings, dashboard isolation.
- NOT IMPLEMENTED: R1, R2, R3, R4, R6, R7, R8, R14. No test pretends otherwise.
- No document may describe issuer trust, signatures, expiry, revocation, action binding, or replay protection as implemented.
