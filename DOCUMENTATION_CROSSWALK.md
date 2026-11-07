# Documentation crosswalk

Status: CURRENT (verified against source and a test in `95e5015` plus working tree), HISTORICAL (true of a past snapshot), INFERRED (follows from design, not tested), DEFERRED (not implemented), UNKNOWN (not verified).

| Claim | Implementation | Documentation | Test | Status |
|---|---|---|---|---|
| Integrity check runs before the verifier; a bad digest never reaches it | `gateway.py` `_judge` order | ARCHITECTURE (trust model); AUTHORITY_CONTRACT s.1, s.5; INVARIANTS | `test_verifier_is_not_called_for_an_artifact_with_a_bad_digest` | CURRENT |
| Verifier returns literal True: accept | `gateway.py` `answer is True` | README; AUTHORITY_CONTRACT s.1 | `test_with_a_verifier_a_registered_grant_is_accepted` | CURRENT |
| Verifier returns literal False: refuse MISSING_AUTHORITY | `gateway.py` `answer is False` | README; ARCHITECTURE; AUTHORITY_CONTRACT s.1, s.5; INVARIANTS; SECURITY | `test_an_explicit_false_is_a_refusal_of_the_grant`; `test_with_a_verifier_an_unverified_grant_is_refused_as_missing_authority` | CURRENT |
| Verifier returns any other value (None, 0, 1, "yes", list, 1.0): refuse AUTHORITY_VERIFIER_UNAVAILABLE | `gateway.py` else branch | README; ARCHITECTURE; AUTHORITY_CONTRACT s.1, s.5 (R11); INVARIANTS; SECURITY | `test_a_malformed_answer_is_a_verifier_failure_not_a_verdict_on_the_grant` (6 cases) | CURRENT |
| Verifier raises: refuse AUTHORITY_VERIFIER_UNAVAILABLE | `gateway.py` except branch | README; ARCHITECTURE; AUTHORITY_CONTRACT; INVARIANTS; SECURITY | `test_a_verifier_that_raises_refuses_the_artifact_as_unavailable`; `..._in_production_refuses_and_never_accepts` | CURRENT |
| Verifier exception text is not in the verdict | `gateway.py` discards exception | SECURITY (verifier trust boundary); AUTHORITY_CONTRACT s.1 | `test_a_verifier_outage_does_not_leak_its_exception_into_the_verdict` | CURRENT |
| Verifier outage never accepts | `gateway.py` | SECURITY; INVARIANTS (verifier semantics) | `test_a_verifier_outage_in_production_refuses_and_never_accepts`; malformed test | CURRENT |
| Verifier receives only Authority (actor, grant) | `gateway.py` call site | README; ARCHITECTURE; AUTHORITY_CONTRACT s.1, s.4 | Signature visible; no test asserts absence of other arguments | CURRENT (by inspection) |
| Verifier cannot bind scope or action | Design of the signature | README; AUTHORITY_CONTRACT s.3 (R6, R7) | None possible (not implemented) | DEFERRED |
| PRODUCTION refuses to construct without a callable verifier | `gateway.py` `__init__` | README; SECURITY; ARCHITECTURE; INVARIANTS | `test_production_without_a_verifier_refuses_to_be_built`; `..._non_callable_...` | CURRENT |
| PRODUCTION checks only that a callable exists, not trustworthiness | `gateway.py` `callable()` | SECURITY; INVARIANTS; README | Behaviour shown by `test_production_accepts_a_verified_actor` (stub verifier) | CURRENT |
| PRODUCTION refuses everything if verifier removed later | `gateway.py` `_judge` | README; AUTHORITY_CONTRACT s.5 | `test_production_with_the_verifier_removed_later_refuses_everything` | CURRENT |
| Profile cannot be downgraded after construction | `gateway.py` read-only property | README | `test_the_profile_cannot_be_downgraded_after_construction` | CURRENT |
| Unknown profile is a ValueError | `gateway.py` | README | `test_an_unknown_profile_refuses_to_be_built` | CURRENT |
| DEVELOPMENT accepts any well-formed authority, including a re-sealed edit | `gateway.py` default | README; ARCHITECTURE; INVARIANTS; SECURITY | `test_default_profile_is_development_and_keeps_the_original_behaviour` | CURRENT |
| Dashboard records after judgment and never changes the verdict | `gateway.py` `evaluate` | ARCHITECTURE; INVARIANTS (dashboard isolation); README | `test_dashboard_never_changes_the_decision` | CURRENT |
| Dashboard `record()` raising keeps an accepted verdict | `gateway.py` try/except | ARCHITECTURE; INVARIANTS | `test_a_failing_dashboard_keeps_an_accepted_verdict_and_logs_it` | CURRENT |
| Dashboard `record()` raising keeps a rejected verdict | `gateway.py` try/except | ARCHITECTURE; INVARIANTS | `test_a_failing_dashboard_keeps_a_rejected_verdict_and_logs_it` | CURRENT |
| Dashboard exception is logged | `gateway.py` `logging...exception` | ARCHITECTURE; INVARIANTS | Both dashboard tests assert a log record with exc_info | CURRENT |
| Dashboard exception text does not reach the verdict | `gateway.py` | ARCHITECTURE | `test_the_dashboard_exception_text_does_not_reach_the_caller_or_the_verdict` | CURRENT |
| Ordinary judging error returns INVALID_ARTIFACT | `gateway.py` outer except | ARCHITECTURE; INVARIANTS (failure rule) | `test_an_unexpected_error_while_judging_is_a_refusal_not_a_crash` | CURRENT |
| Artifact cannot be built with cyclic payload (RecursionError) | `models.py` `_freeze` | README; INVARIANTS (construction boundary) | `test_a_payload_that_contains_itself_cannot_be_sealed` | CURRENT |
| Artifact cannot be built nested ~5,000 deep | `models.py` recursion | README; INVARIANTS | `test_a_payload_nested_past_the_recursion_limit_cannot_be_sealed` | CURRENT |
| Oversized payload is judged; one-element change refused | `models.py` digest | INVARIANTS | `test_an_oversized_payload_is_judged_and_a_change_to_one_element_is_refused` | CURRENT |
| Mapping subclass whose items() raises cannot be sealed | `models.py` | README | `test_a_mapping_subclass_whose_items_raise_cannot_be_sealed` | CURRENT |
| Integrity is unkeyed SHA-256 over six fields in canonical JSON | `models.py` `_digest_fields`, `_canonical` | README; INVARIANTS (exact form); SECURITY | `test_integrity_detects_mutation_after_hashing`; `test_forged_integrity_is_rejected` | CURRENT |
| Digest is not authenticity; attacker who replaces data and digest passes | Design | INVARIANTS; SECURITY; ARCHITECTURE | `test_authority_tampering_is_rejected` shows detection only for unresealed edits; re-sealed edit accepted in DEVELOPMENT (test above) | CURRENT |
| Canonical JSON options (sorted keys, compact separators, ensure_ascii False) | `models.py` `json.dumps` | INVARIANTS | Not tested individually | INFERRED from code inspection |
| NaN and infinity refused | `models.py` allow_nan=False | INVARIANTS; README | `test_nan_payload_is_rejected_instead_of_getting_ambiguous_integrity` | CURRENT |
| Non-string mapping keys refused | `models.py` `_freeze` | README; INVARIANTS | `test_non_string_mapping_keys_cannot_be_silently_coerced` | CURRENT |
| Payload is frozen (API guarantee, not a security boundary) | `models.py` MappingProxyType | README; INVARIANTS | `test_nested_payload_is_immutable`; `test_artifact_is_immutable_at_top_level` | CURRENT (API only) |
| Scope is validated and preserved, not enforced | `gateway.py` enum check | README; INVARIANTS (scope); SECURITY | `test_scope_broadening_is_rejected` (integrity only) | CURRENT (validation); enforcement NOT IMPLEMENTED in package |
| A refusal is a return value; callers can ignore it | Library design | INVARIANTS; SECURITY; ARCHITECTURE | None possible in package | INFERRED |
| Accepted does not mean authenticated, authorized, or safe to execute | Design | INVARIANTS "What acceptance means" | Covered indirectly by unsealed-edit acceptance test | INFERRED (documented) |
| Authority presence is not proof of issuance | `models.py` Authority | README; INVARIANTS; SECURITY | `test_capability_does_not_equal_authority` | CURRENT |
| Refusal vocabulary: seven codes | `models.py` `GateReason` | README (list) | `test_the_corpus_reaches_every_reason_the_gateway_can_give` | CURRENT |
| GOVERNANCE_VIOLATION removed | `models.py` | README (removal note) | Corpus test; `git grep` finds no code references | CURRENT |
| Expiry and revocation: not implemented; revocation bounded by grant lifetime (decision B) | None in package | AUTHORITY_CONTRACT s.2, s.3, s.6; README; SECURITY | None (no mechanism to test) | DEFERRED |
| Issuer pinning, signature verification | None | AUTHORITY_CONTRACT; SECURITY | None | DEFERRED |
| Replay protection | None | AUTHORITY_CONTRACT; SECURITY | None | DEFERRED |
| No durable refusal log; no service | Design | README; SECURITY | None possible | CURRENT (by inspection) |
| CNS connector lazy-imports `cns.gate` | `cns_connector.py` `_cns_gate` | README; connector docstring | `test_importing_the_package_loads_nothing_from_cns`; `test_the_package_and_its_connector_import_with_cns_blocked` | CURRENT |
| Connector refuses an installed CNS missing required names | `cns_connector.py` `_REQUIRED_NAMES` | README; connector docstring | `test_a_cns_that_is_too_old_is_refused_at_construction_not_on_first_use` | CURRENT (names only) |
| Connector error text no longer states a version number | `cns_connector.py` message | README | `test_the_connector_says_what_is_missing_when_cns_is_blocked` | CURRENT |
| CNS minimum version 1.2.0 or 1.4.0 | None (names checked, no version check) | README (labelled unverified); connector comment | None | UNKNOWN |
| Tested and pinned CNS version is 2.3.0 | `pyproject.toml` extra | README (compatibility labels); pyproject | `test_the_package_declares_no_runtime_dependency_and_pins_the_cns_extra` | CURRENT |
| Verified compatibility range is 2.3.0 only | Test matrix | README | Tests run only against 2.3.0 | CURRENT |
| Verdicts bound to judged content by CNS subject_digest | `cns_connector.py` `judged_content` | README; connector docstring | `test_every_verdict_is_bound_to_the_candidate_it_judged`; `test_a_verdict_does_not_bind_to_a_different_artifact` | CURRENT |
| Digest covers stored integrity string | `cns_connector.py` `_JUDGED_FIELDS` | connector docstring | `test_a_pass_on_a_valid_artifact_does_not_bind_to_a_copy_with_a_forged_integrity` | CURRENT |
| Depth limit 32 and expanded-value limit 10,000 | `cns_connector.py` constants | connector docstring; README | `test_the_bounds_are_the_documented_ones`; `test_the_bound_is_exactly_the_documented_depth` | CURRENT |
| Cycles and shared nodes handled without unbounded work | `cns_connector.py` walk | connector docstring | `test_a_container_that_contains_itself_makes_its_whole_field_a_cycle`; `test_work_is_bounded_by_what_is_distinct_not_by_what_is_shared` | CURRENT |
| Hostile subclasses digested as plain values | `cns_connector.py` `_text`, `_scalar` | connector docstring | `test_a_hostile_subclass_is_digested_as_the_plain_value_it_holds` | CURRENT |
| Inconsistent native verdict never maps to PASS | `cns_connector.py` `to_cns_result` | connector docstring; README | `test_a_self_contradicting_native_verdict_never_maps_to_pass` | CURRENT |
| Connector never emits RETRY | `cns_connector.py` | connector docstring; README | `test_no_verdict_is_ever_a_retry` | CURRENT |
| Re-judgment in connector does not touch the dashboard | `cns_connector.py` `_judge` | connector docstring | `test_the_rejudgment_does_not_touch_an_attached_dashboard` | CURRENT |
| Exceptions from the gateway propagate; never PASS | `cns_connector.py` | connector docstring | `test_an_error_inside_the_gateway_propagates_and_is_never_a_pass` | CURRENT |
| Chain is admission-only; complete() is False | `cns_connector.py` | README; connector docstring | `test_the_chain_is_admission_only_and_says_so` | CURRENT |
| Live decision path and evidence spine are separate workflows | Architecture | README | None (documentation structure) | INFERRED |
| Repository tests: 465 (CNS present), 274 + 1 skipped (CNS absent) | Test suite | README maturity | Measured this pass | CURRENT (local, uncommitted tree) |
| CI green on main `d7b2749` | GitHub check runs | README release table | Verified via API this pass (test 3.11, 3.12; cns 3.11, 3.12 success) | CURRENT |
| CI green on `cd9cc62` | GitHub (earlier) | README (labelled historical) | Earlier session | HISTORICAL |
| Spine run 2026-11-07, 56 scenarios, exit 0, 3 GAPs, Gateway at 1bede83 | CNS script | README spine section | Not re-run | HISTORICAL / UNKNOWN |
| Python 3.11+ floor; sibling projects 3.10 or newer | pyproject (3.11) | README | Sibling claim not re-checked | UNKNOWN (sibling part) |
| Private vulnerability reporting | SECURITY link | SECURITY | Not testable | INSPECTED |
