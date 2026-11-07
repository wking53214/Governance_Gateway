# Adversarial test report

Results are from the local run this pass: 465 passed with CNS present; 274 passed and 1 skipped with CNS absent. "PASS" means the named test ran and passed.

| Test case | Threat or failure mode | Expected behaviour | Actual result | PASS/FAIL | Limitation |
|---|---|---|---|---|---|
| Payload tampering after sealing | Edit payload, keep digest | INTEGRITY_FAILURE | INTEGRITY_FAILURE | PASS (`test_payload_tampering_is_rejected`) | Detects unresealed edits only |
| Provenance tampering | Edit provenance | INTEGRITY_FAILURE | INTEGRITY_FAILURE | PASS (`test_provenance_tampering_is_rejected`) | Same |
| Authority tampering | Swap authority | INTEGRITY_FAILURE | INTEGRITY_FAILURE | PASS (`test_authority_tampering_is_rejected`) | Same |
| Scope tampering (broadening) | READ_ONLY to EXECUTE | INTEGRITY_FAILURE | INTEGRITY_FAILURE | PASS (`test_scope_broadening_is_rejected`) | Same |
| Epistemic-status tampering | Change status | INTEGRITY_FAILURE | INTEGRITY_FAILURE | PASS (`test_no_epistemic_promotion`; integrity tests) | Same |
| Stored digest tampering | Replace integrity with zeros | INTEGRITY_FAILURE | INTEGRITY_FAILURE | PASS (`test_forged_integrity_is_rejected`) | Same |
| Malformed digest | Non-hex or wrong length | INTEGRITY_FAILURE | INTEGRITY_FAILURE | PASS (`test_integrity_must_be_lowercase_hex_sha256`) | None |
| Re-sealed malicious artifact (DEVELOPMENT) | Edit then recompute digest | Accepted (documented) | Accepted | PASS (`test_default_profile_is_development_and_keeps_the_original_behaviour`) | Unkeyed digest: by design |
| Re-sealed malicious artifact (PRODUCTION, unverified actor) | Edit, reseal, wrong actor | MISSING_AUTHORITY | MISSING_AUTHORITY | PASS (`test_production_refuses_a_resealed_edit_from_an_unverified_actor`) | Depends on verifier |
| Missing authority | authority=None | MISSING_AUTHORITY | MISSING_AUTHORITY | PASS (`test_gateway_does_not_create_authority`) | None |
| Invalid authority | Blank actor | ValueError at construction | ValueError | PASS (`test_gateway.py` authority construction) | None |
| Trusted verifier | Verifier returns True | Accept | Accept | PASS (`test_with_a_verifier_a_registered_grant_is_accepted`) | None |
| Rejected verifier | Verifier returns False | MISSING_AUTHORITY | MISSING_AUTHORITY | PASS (`test_an_explicit_false_is_a_refusal_of_the_grant`) | None |
| Verifier exception | Verifier raises | AUTHORITY_VERIFIER_UNAVAILABLE | AUTHORITY_VERIFIER_UNAVAILABLE | PASS (`test_a_verifier_that_raises_refuses_the_artifact_as_unavailable`) | None |
| Verifier exception leaks secret | Exception text contains secret | Secret absent from verdict | Absent | PASS (`test_a_verifier_outage_does_not_leak_its_exception_into_the_verdict`) | Secret still exists in the exception object for the caller |
| Verifier returns None | None | AUTHORITY_VERIFIER_UNAVAILABLE | AUTHORITY_VERIFIER_UNAVAILABLE | PASS (malformed test) | Classification choice |
| Verifier returns non-boolean (0, 1, "yes", [True], 1.0) | Truthy or odd values | AUTHORITY_VERIFIER_UNAVAILABLE | AUTHORITY_VERIFIER_UNAVAILABLE | PASS (malformed test, 5 cases) | Classification choice |
| Production without verifier | Construct PRODUCTION alone | ValueError | ValueError | PASS (`test_production_without_a_verifier_refuses_to_be_built`) | None |
| Production with non-callable verifier | `True`, `"verify"`, `1`, `object()` | ValueError | ValueError | PASS (`test_production_with_a_non_callable_verifier_refuses_to_be_built`) | None |
| Production with verifier removed later | Set verifier None after construction | MISSING_AUTHORITY | MISSING_AUTHORITY | PASS (`test_production_with_the_verifier_removed_later_refuses_everything`) | None |
| Production verifier outage | Verifier raises in PRODUCTION | Refuse, never accept | AUTHORITY_VERIFIER_UNAVAILABLE | PASS (`test_a_verifier_outage_in_production_refuses_and_never_accepts`) | None |
| Bad digest never reaches verifier | Tampered artifact with recording verifier | Verifier not called | Not called | PASS (`test_verifier_is_not_called_for_an_artifact_with_a_bad_digest`) | None |
| Dashboard success | Normal recording | Counted, verdict unchanged | As expected | PASS (`test_accept_is_counted`; `test_dashboard_never_changes_the_decision`) | None |
| Dashboard exception after acceptance | record() raises on accepted artifact | Accept kept; exception logged; not raised | As expected | PASS (`test_a_failing_dashboard_keeps_an_accepted_verdict_and_logs_it`) | Log content not checked beyond message and exc_info |
| Dashboard exception after rejection | record() raises on rejected artifact | Reject kept; exception logged; not raised | As expected | PASS (`test_a_failing_dashboard_keeps_a_rejected_verdict_and_logs_it`) | Same |
| Dashboard exception text | Secret in dashboard exception | Not in verdict | Not in verdict | PASS (`test_the_dashboard_exception_text_does_not_reach_the_caller_or_the_verdict`) | Still written to logs by design |
| CNS absent | cns not importable | Gateway works; connector raises CnsNotInstalled | As expected | PASS (`test_the_package_and_its_connector_import_with_cns_blocked`; `test_the_gateway_still_judges_artifacts_with_cns_blocked`) | None |
| CNS incompatible (missing names) | cns.gate lacks names | Refused at construction | As expected | PASS (`test_a_cns_that_is_too_old_is_refused_at_construction_not_on_first_use`) | Names only; no version check |
| CNS import failure | cns.gate raises on import | Reported as broken | As expected | PASS (`test_a_cns_that_fails_to_import_is_reported_as_broken_not_as_missing`) | None |
| Invalid gate contract | Double with wrong shape | Not a PASS | As expected | PASS (`test_the_double_is_no_looser_than_the_real_contract`) | Test double, not real CNS |
| Malformed native verdict | Non-bool accepted | TERMINAL_BREACH INCONSISTENT_VERDICT | As expected | PASS (`test_something_that_is_not_a_native_verdict_is_an_error_not_a_pass`) | None |
| Contradictory native verdict | Accept with reason | Not PASS | As expected | PASS (`test_a_self_contradicting_native_verdict_never_maps_to_pass`) | None |
| Verdict for another artifact | Binding mismatch | Not PASS | As expected | PASS (`test_a_verdict_does_not_bind_to_another_artifact_or_a_drifted_one`) | None |
| Deep content | Nested beyond 32 | Summarised by digest; still bound | As expected | PASS (`test_a_payload_nested_past_what_cns_can_render_is_still_judged_and_bound`) | None |
| Oversized content | More than 10,000 values | Summarised; drift detected | As expected | PASS (`test_a_pass_never_binds_to_a_copy_that_drifted_inside_a_payload_larger_than_the_bound`) | None |
| Cycles | Self-containing container | Whole field `{"cycle": true}` | As expected | PASS (`test_a_container_that_contains_itself_makes_its_whole_field_a_cycle`) | Gateway itself cannot seal cycles (see Artifact construction tests) |
| Shared nodes | Same object referenced twice | Digests like copies; bounded work | As expected | PASS (`test_a_shared_value_is_not_a_cycle_and_digests_like_its_copies`; `test_work_is_bounded_by_what_is_distinct_not_by_what_is_shared`) | None |
| Hostile subclasses | Subclass overriding dunders | Digested as plain values | As expected | PASS (`test_a_hostile_subclass_is_digested_as_the_plain_value_it_holds`) | None |
| Digest drift | Content changes after verdict | Verdict no longer binds | As expected | PASS (`test_content_drifting_after_the_verdict_no_longer_binds`) | None |
| Artifact construction: cyclic payload | Self-containing list | RecursionError | RecursionError | PASS (`test_a_payload_that_contains_itself_cannot_be_sealed`) | Exception type is RecursionError, not ValueError |
| Artifact construction: 5,000-deep payload | Deep nesting | RecursionError | RecursionError | PASS (`test_a_payload_nested_past_the_recursion_limit_cannot_be_sealed`) | Depends on interpreter limit |
| Artifact construction: 200,000 elements | Oversized payload | Judged; one change refused | As expected | PASS (`test_an_oversized_payload_is_judged_and_a_change_to_one_element_is_refused`) | None |

## Not tested (deliberately)

- Revoked grant refused: no revocation mechanism exists.
- Expired grant refused by the package: no expiry field exists.
- Unknown issuer, invalid signature, wrong action, wrong scope, replay: no mechanism exists. No test pretends otherwise.
- Real CNS versions other than 2.3.0.

## Summary

Every executed case passes. Failures found during this pass: none. The one behaviour change (malformed answers now AUTHORITY_VERIFIER_UNAVAILABLE) is documented in AUTHORITY_CONTRACT and README.
