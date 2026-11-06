| Original | Caso de integración | Resultado / alcance |
|---|---|---|
| `tests/test_clinician_access.py:79::test_clinician_without_relationship_gets_403_everywhere_and_is_audited` | `test_clinician_without_relationship_gets_403_everywhere_and_is_audited` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_clinician_access.py:112::test_clinicians_with_relationship_have_access` | `test_clinicians_with_relationship_have_access` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_clinician_correction.py:70::test_clinician_correction_reaches_series_and_report` | `test_clinician_correction_reaches_series_and_report` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_clinician_validation.py:87::test_invalid_corrections_are_rejected_and_nothing_changes` | `test_invalid_corrections_are_rejected_and_nothing_changes` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_clinician_validation.py:139::test_correction_is_reflected_in_extraction_panels` | `test_correction_is_reflected_in_extraction_panels` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_clinician_validation.py:170::test_clinical_rejection_does_not_fail_and_invalidates_markers` | `test_clinical_rejection_does_not_fail_and_invalidates_markers` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_clinician_validation.py:190::test_validation_without_corrections_does_not_recompute_score` | `test_validation_without_corrections_does_not_recompute_score` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_extraction_flow.py:39::test_complete_extraction_and_confirmation_flow` | `test_complete_extraction_and_confirmation_flow` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_extraction_proposal.py:70::test_proposal_block_is_immutable` | `test_proposal_block_is_immutable` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_extraction_proposal.py:107::test_reprocess_creates_a_new_proposal_and_keeps_the_old_one` | `test_reprocess_creates_a_new_proposal_and_keeps_the_old_one` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_extraction_proposal.py:126::test_clinical_letter_is_not_applicable_but_downloadable` | `test_clinical_letter_is_not_applicable_but_downloadable` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_extraction_rules.py:80::test_get_extraction_rules` | `test_get_extraction_rules` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_extraction_rules.py:112::test_confirm_rules_state_idempotency_and_summary` | `test_confirm_rules_state_idempotency_and_summary` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_extraction_rules.py:146::test_value_implausible_is_rejected` | `test_value_implausible_is_rejected` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_extraction_rules.py:160::test_reprocess_rules` | `test_reprocess_rules` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_extraction_rules.py:200::test_reprocess_limit_per_exam` | `test_reprocess_limit_per_exam` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_full_lifecycle.py:42::test_endpoints_5_to_11_lifecycle` | `test_endpoints_5_to_11_lifecycle` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_lab_report.py:76::test_lab_report_endpoint_19` | `test_lab_report_endpoint_19` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_lab_report.py:145::test_lab_report_validation_and_empty` | `test_lab_report_validation_and_empty` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_lab_report_export.py:77::test_export_lab_report_endpoint_20` | `test_export_lab_report_endpoint_20` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_lab_report_export.py:132::test_export_lab_report_validation` | `test_export_lab_report_validation` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_markers_series.py:72::test_marker_series_endpoint_17` | `test_marker_series_endpoint_17` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_markers_series.py:106::test_marker_series_validation` | `test_marker_series_validation` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_recompute_batch.py:38::test_bulk_recompute_dry_run_vs_apply` | `test_bulk_recompute_dry_run_vs_apply` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_scoring_flow.py:82::test_full_scoring_flow_and_endpoint_18` | `test_full_scoring_flow_and_endpoint_18` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_scoring_flow.py:212::test_lab_score_no_score_available` | `test_lab_score_no_score_available` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_scoring_reproducibility.py:106::test_same_input_gives_same_output` | `test_same_input_gives_same_output` | PASS; original pure function; no Mongo/HTTP |
| `tests/test_scoring_reproducibility.py:113::test_subscore_is_always_between_0_and_100` | `test_subscore_is_always_between_0_and_100` | PASS; original pure function; no Mongo/HTTP |
| `tests/test_scoring_reproducibility.py:136::test_recomputing_with_the_same_inputs_gives_the_same_score` | `test_recomputing_with_the_same_inputs_gives_the_same_score` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
| `tests/test_upload_flow.py:23::test_full_upload_flow` | `test_full_upload_flow` | PASS; real Mongo + HTTP + workers; explicit object/AI/scanner doubles |
