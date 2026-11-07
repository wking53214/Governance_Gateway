# Authority requirements matrix

Source of requirements: `docs/AUTHORITY_CONTRACT.md` (section 3). Status labels: EXECUTED, INSPECTED, INFERRED, UNKNOWN, NOT IMPLEMENTED.

"Result" is the result of the named test in this session (459 passed with CNS; 268 passed without). A requirement marked NOT IMPLEMENTED has no test, deliberately.

| Requirement | Implementation status | Relevant source | Test name | Result | Deferred dependency |
|---|---|---|---|---|---|
| R1 Trusted issuer identity pinned by operator | NOT IMPLEMENTED | none (no issuer concept) | none | n/a | Operator key file and verifier; decision A |
| R2 Grant signature verified against issuer | NOT IMPLEMENTED | none (`Authority.grant` is a string) | none | n/a | Key management, signing scheme; out of scope for this package |
| R3 Expired grants refused | NOT IMPLEMENTED in the package | none (no expiry field) | none | n/a | Expiry in the grant and in the verifier |
| R4 Revoked grants refused at decision time | NOT IMPLEMENTED; contract changed to bounded revocation (decision B) | none | none | n/a | Revocation feed or registry, not built; decision B accepts grant-lifetime bound |
| R5 Grant covers this actor | IMPLEMENTED (caller-supplied) | `gateway.py` verifier call; `models.py` Authority | `test_with_a_verifier_an_unverified_grant_is_refused_as_missing_authority`; `test_with_a_verifier_a_registered_grant_is_accepted`; `test_production_accepts_a_verified_actor` | EXECUTED | Verifier must check actor |
| R6 Grant covers this action | NOT IMPLEMENTED | none (no action in `Artifact`) | none | n/a | Action model in `Artifact` and verifier request |
| R7 Grant covers artifact scope | NOT IMPLEMENTED | none (verifier gets no scope) | none | n/a | Verifier request object (R14) |
| R8 Replay protection | NOT IMPLEMENTED | none | none | n/a | Nonce store, state |
| R9 Verifier unavailable refuses | IMPLEMENTED | `gateway.py` except branch | `test_a_verifier_that_raises_refuses_the_artifact_as_unavailable`; `test_a_verifier_outage_in_production_refuses_and_never_accepts` | EXECUTED | None |
| R10 Verifier exception does not prove grant invalid | IMPLEMENTED | `models.py` `AUTHORITY_VERIFIER_UNAVAILABLE`; `gateway.py` | `test_a_verifier_outage_does_not_leak_its_exception_into_the_verdict`; `test_a_verifier_that_answers_false_is_a_refusal_not_an_outage` | EXECUTED | None |
| R11 Non-boolean answer refuses | IMPLEMENTED (as `MISSING_AUTHORITY`; no separate malformed code) | `gateway.py` `answer is not True` | `test_only_a_true_answer_counts_as_verified` | EXECUTED | Separate code is an assumption (Section 6 of report) |
| R12 Tampered artifact never reaches verifier | IMPLEMENTED | `gateway.py` order | `test_verifier_is_not_called_for_an_artifact_with_a_bad_digest`; `test_the_verifier_does_not_override_an_earlier_refusal` | EXECUTED | None |
| R13 Production profile refuses without verifier | IMPLEMENTED | `gateway.py` `__init__` and `_judge` | `test_production_without_a_verifier_refuses_to_be_built`; `test_production_with_the_verifier_removed_later_refuses_everything` | EXECUTED | Checks existence, not trust |
| R14 Verifier request object with artifact context | NOT IMPLEMENTED | none | none | n/a | Public-API change; deferred |
| Verifier interface `authority_verifier(Authority) -> bool` | IMPLEMENTED | `gateway.py` | `test_with_no_verifier_any_authority_is_accepted` and others | EXECUTED | None |
| Development profile behaves as documented | IMPLEMENTED | `gateway.py` | `test_default_profile_is_development_and_keeps_the_original_behaviour`; `test_with_no_verifier_any_authority_is_accepted` | EXECUTED | None |
| Production profile behaves as documented | IMPLEMENTED | `gateway.py` | `test_production_refuses_a_resealed_edit_from_an_unverified_actor`; `test_production_accepts_a_verified_actor` | EXECUTED | None |
| Malformed verification request | NOT APPLICABLE (the request is an `Authority`, already validated at construction) | `models.py` `Authority.__post_init__` | `test_gateway_does_not_create_authority`; Authority construction tests in `test_gateway.py` | EXECUTED | None |
| Tampered artifact never reaches verifier (acceptance list) | IMPLEMENTED | as R12 | as R12 | EXECUTED | None |
| Verifier returns None, string, other non-boolean | IMPLEMENTED | as R11 | `test_only_a_true_answer_counts_as_verified` | EXECUTED | None |
| Verifier raises an exception | IMPLEMENTED | as R9 | as R9 | EXECUTED | None |
| Unknown issuer rejected | NOT IMPLEMENTED | none | none | n/a | R1 |
| Invalid signature rejected | NOT IMPLEMENTED | none | none | n/a | R2 |
| Expired grant rejected | NOT IMPLEMENTED in the package | none | none | n/a | R3 |
| Wrong actor rejected | IMPLEMENTED via verifier | as R5 | `test_with_a_verifier_an_unverified_grant_is_refused_as_missing_authority` | EXECUTED | Relies on the caller's verifier |
| Wrong scope rejected | NOT IMPLEMENTED | none | none | n/a | R7 |
| Wrong action rejected | NOT IMPLEMENTED | none | none | n/a | R6 |
| Replay refused | NOT IMPLEMENTED | none | none | n/a | R8 |
| Verifier unavailable refuses | IMPLEMENTED | as R9 | as R9 | EXECUTED | None |
| Deep and oversized content, tampered copy | IMPLEMENTED | `models.py`, `cns_connector.py` | `test_an_oversized_payload_is_judged_and_a_change_to_one_element_is_refused`; `test_a_deep_artifact_the_gateway_accepts_does_not_let_a_tampered_copy_bind` | EXECUTED | None |
| Hostile subclass | IMPLEMENTED (refused at construction when inspection raises) | `models.py` | `test_a_mapping_subclass_whose_items_raise_cannot_be_sealed`; `test_subclass_integrity_bypass_blocked` | EXECUTED | None |
| Dashboard failure cannot change the verdict | IMPLEMENTED | `gateway.py` `evaluate` | `test_a_failing_dashboard_does_not_change_the_verdict_or_raise` | EXECUTED | None |

## Summary

- IMPLEMENTED with tests: R5 (caller-supplied), R9, R10, R11, R12, R13, and the verifier interface.
- NOT IMPLEMENTED: R1, R2, R3, R4, R6, R7, R8, R14. No test pretends otherwise.
- The authority contract may not be described as implementing issuer trust, signatures, expiry, revocation, action binding or replay protection in any document.
