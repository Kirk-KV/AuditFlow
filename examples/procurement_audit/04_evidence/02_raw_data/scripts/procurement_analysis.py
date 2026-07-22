from __future__ import annotations

from pathlib import Path

import pandas as pd


OUTPUT_FILES = {
    "t001_candidates": "t001_release_before_approval_candidates.csv",
    "t001_review": "t001_release_before_approval_review.csv",
    "t002_exceptions": "t002_approval_authority_exceptions.csv",
    "t003_invoice_groups": "t003_duplicate_invoice_groups.csv",
    "t003_invoice_records": "t003_duplicate_invoice_candidate_records.csv",
    "t003_payment_groups": "t003_repeated_payment_amount_groups.csv",
    "t003_review": "t003_duplicate_payment_review.csv",
    "t004_candidates": "t004_split_purchase_candidates.csv",
    "t004_review": "t004_split_purchase_review.csv",
}


def load_datasets(project_root: Path) -> dict[str, pd.DataFrame]:
    raw_dir = project_root / "04_evidence" / "02_raw_data"
    data = {path.stem: pd.read_csv(path) for path in sorted(raw_dir.glob("*.csv"))}

    for frame in data.values():
        for column in frame.columns:
            if column.endswith("_date"):
                frame[column] = pd.to_datetime(frame[column], errors="coerce")

    return data


def _approval_tests(data: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    purchase_orders = data["purchase_orders"]
    approval_workflow = data["approval_workflow"]
    users = data["users"]
    suppliers = data["suppliers"]

    approval_base = (
        purchase_orders.merge(approval_workflow, on="po_id", suffixes=("", "_workflow"))
        .merge(
            users[["user_id", "name", "approval_role", "approval_limit"]],
            left_on="approver_user_id",
            right_on="user_id",
            how="left",
        )
        .merge(
            suppliers[["supplier_id", "supplier_name"]],
            on="supplier_id",
            how="left",
        )
    )
    approval_base["released_before_approval"] = (
        approval_base["release_date"] < approval_base["approval_date"]
    )
    approval_base["insufficient_approval_limit"] = (
        approval_base["amount"] > approval_base["approval_limit"]
    )

    t001 = approval_base.loc[
        approval_base["released_before_approval"],
        [
            "po_id",
            "supplier_name",
            "amount",
            "created_date",
            "release_date",
            "approval_date",
            "approver_user_id",
            "name",
            "approval_role",
            "approval_limit",
            "required_approval_role",
        ],
    ].sort_values(["release_date", "po_id"])
    t001.insert(0, "candidate_id", "T001-" + t001["po_id"])

    t002 = approval_base.loc[
        approval_base["insufficient_approval_limit"],
        [
            "po_id",
            "supplier_name",
            "amount",
            "approval_date",
            "approver_user_id",
            "name",
            "approval_role",
            "approval_limit",
            "required_approval_role",
        ],
    ].sort_values(["approval_date", "po_id"])
    t002.insert(0, "candidate_id", "T002-" + t002["po_id"])

    return t001, t002


def _duplicate_payment_tests(
    data: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    invoices = data["invoices"]
    payments = data["payments"]
    suppliers = data["suppliers"]

    invoice_groups = (
        invoices.groupby(["supplier_id", "invoice_number"])
        .size()
        .reset_index(name="invoice_count")
        .query("invoice_count > 1")
        .merge(suppliers[["supplier_id", "supplier_name"]], on="supplier_id", how="left")
        .sort_values(["supplier_id", "invoice_number"])
        .reset_index(drop=True)
    )
    invoice_groups.insert(
        0,
        "candidate_id",
        [f"T003-I-{index:03d}" for index in range(1, len(invoice_groups) + 1)],
    )

    if invoice_groups.empty:
        invoice_records = invoices.head(0).copy()
        invoice_records.insert(0, "candidate_id", pd.Series(dtype="object"))
    else:
        invoice_records = (
            invoices.merge(
                invoice_groups[["candidate_id", "supplier_id", "invoice_number"]],
                on=["supplier_id", "invoice_number"],
                how="inner",
            )
            .merge(
                suppliers[["supplier_id", "supplier_name"]],
                on="supplier_id",
                how="left",
            )
            .sort_values(["candidate_id", "invoice_date", "invoice_id"])
        )

    payment_groups = (
        payments.groupby(["supplier_id", "amount"])
        .agg(
            payment_count=("payment_id", "count"),
            payment_ids=("payment_id", lambda values: ", ".join(values)),
        )
        .reset_index()
        .query("payment_count > 1")
        .merge(suppliers[["supplier_id", "supplier_name"]], on="supplier_id", how="left")
        .sort_values(["supplier_id", "amount"])
        .reset_index(drop=True)
    )
    payment_groups.insert(
        0,
        "candidate_id",
        [f"T003-P-{index:03d}" for index in range(1, len(payment_groups) + 1)],
    )

    invoice_review = invoice_groups.assign(candidate_type="duplicate_invoice_number")[
        ["candidate_id", "candidate_type", "supplier_id", "supplier_name"]
    ]
    payment_review = payment_groups.assign(candidate_type="repeated_payment_amount")[
        ["candidate_id", "candidate_type", "supplier_id", "supplier_name"]
    ]
    review_candidates = pd.concat([invoice_review, payment_review], ignore_index=True)

    return invoice_groups, invoice_records, payment_groups, review_candidates


def _split_purchase_test(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    purchase_orders = data["purchase_orders"]
    suppliers = data["suppliers"]
    users = data["users"]
    threshold = 100_000
    window_days = 3
    min_po_count = 3
    rows: list[dict[str, object]] = []

    grouped = purchase_orders.sort_values("created_date").groupby(
        ["supplier_id", "requester_user_id"]
    )
    for (supplier_id, requester_user_id), group in grouped:
        group = group.sort_values("created_date")
        for _, row in group.iterrows():
            window_start = row["created_date"]
            window_end = window_start + pd.Timedelta(days=window_days)
            window = group[
                (group["created_date"] >= window_start)
                & (group["created_date"] <= window_end)
            ]
            if (
                len(window) >= min_po_count
                and window["amount"].max() < threshold
                and window["amount"].sum() > threshold
            ):
                rows.append(
                    {
                        "supplier_id": supplier_id,
                        "requester_user_id": requester_user_id,
                        "window_start": window_start.date().isoformat(),
                        "window_end": window_end.date().isoformat(),
                        "po_ids": ", ".join(window["po_id"].tolist()),
                        "po_count": len(window),
                        "total_amount": round(window["amount"].sum(), 2),
                        "max_single_amount": round(window["amount"].max(), 2),
                    }
                )

    candidates = pd.DataFrame(rows)
    if not candidates.empty:
        candidates = (
            candidates.drop_duplicates(
                subset=["supplier_id", "requester_user_id", "po_ids"]
            )
            .merge(
                suppliers[["supplier_id", "supplier_name"]],
                on="supplier_id",
                how="left",
            )
            .merge(
                users[["user_id", "name"]],
                left_on="requester_user_id",
                right_on="user_id",
                how="left",
            )
            .rename(columns={"name": "requester_name"})
            .sort_values(["supplier_id", "window_start", "po_ids"])
            .reset_index(drop=True)
        )
    candidates.insert(
        0,
        "candidate_id",
        [f"T004-{index:03d}" for index in range(1, len(candidates) + 1)],
    )
    return candidates


def _apply_review(
    project_root: Path,
    test_id: str,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    review_path = (
        project_root
        / "04_evidence"
        / "03_correspondence"
        / "candidate_review_dispositions.csv"
    )
    dispositions = pd.read_csv(review_path).query("test_id == @test_id").copy()

    expected = set(candidates["candidate_id"])
    documented = set(dispositions["candidate_id"])
    if expected != documented:
        missing = sorted(expected - documented)
        unexpected = sorted(documented - expected)
        raise ValueError(
            f"Disposition mismatch for {test_id}: missing={missing}, unexpected={unexpected}"
        )

    return candidates.merge(
        dispositions.drop(columns=["test_id"]),
        on="candidate_id",
        how="left",
        validate="one_to_one",
    )


def run_test_analysis(
    project_root: Path,
    *,
    write_outputs: bool = True,
) -> dict[str, pd.DataFrame]:
    project_root = project_root.resolve()
    data = load_datasets(project_root)
    t001, t002 = _approval_tests(data)
    invoice_groups, invoice_records, payment_groups, t003_candidates = (
        _duplicate_payment_tests(data)
    )
    t004 = _split_purchase_test(data)

    outputs = {
        "t001_candidates": t001,
        "t001_review": _apply_review(project_root, "T-001", t001),
        "t002_exceptions": t002,
        "t003_invoice_groups": invoice_groups,
        "t003_invoice_records": invoice_records,
        "t003_payment_groups": payment_groups,
        "t003_review": _apply_review(project_root, "T-003", t003_candidates),
        "t004_candidates": t004,
        "t004_review": _apply_review(project_root, "T-004", t004),
    }

    if write_outputs:
        generated_dir = project_root / "04_evidence" / "99_generated"
        generated_dir.mkdir(parents=True, exist_ok=True)
        for key, frame in outputs.items():
            frame.to_csv(generated_dir / OUTPUT_FILES[key], index=False)

    return outputs


if __name__ == "__main__":
    project = Path(__file__).resolve().parents[3]
    results = run_test_analysis(project)
    for output_key, output_frame in results.items():
        print(f"{OUTPUT_FILES[output_key]}: {len(output_frame)} rows")
