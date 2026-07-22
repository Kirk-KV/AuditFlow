from auditflow.commands.audit_program import build_audit_program


def test_audit_program_regeneration_keeps_planning_fields_only() -> None:
    planning_decision = {
        "included_risks": [
            {"id": "R-001", "title": "Unauthorized purchase", "reasoning": "Key risk"}
        ],
        "controls": [
            {
                "id": "C-001",
                "risk_id": "R-001",
                "description": "Approval before release",
            }
        ],
    }
    existing_program = {
        "program_rows": [
            {
                "test_id": "T-001",
                "risk_id": "R-001",
                "control_id": "C-001",
                "test_hypothesis": "An unauthorized purchase may occur.",
                "test_script": ["Inspect the population."],
                "analysis_refs": ["scripts/test.py"],
                "output_refs": ["outputs/result.csv"],
                "evidence_refs": ["evidence/source.csv"],
                "workpaper_ref": "WP-C-001",
            }
        ]
    }

    program = build_audit_program(planning_decision, existing_program)
    row = program["program_rows"][0]

    assert row["test_hypothesis"] == "An unauthorized purchase may occur."
    assert row["test_script"] == ["Inspect the population."]
    assert "analysis_refs" not in row
    assert "output_refs" not in row
    assert "evidence_refs" not in row
