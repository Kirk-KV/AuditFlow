-- Synthetic data extraction script for LSJC Procurement Process Audit
-- This script is illustrative only. It shows the intended data extraction logic.
-- The generated CSV files in 05_data/raw/ represent the output of this extraction.

-- Audit period parameters
-- :period_from = '2026-01-01'
-- :period_to   = '2026-04-01'

-- 1. Users and approval roles
SELECT
    u.user_id,
    u.full_name AS name,
    u.job_title AS role,
    u.department,
    ar.approval_role,
    ar.approval_limit
FROM erp_users u
LEFT JOIN approval_roles ar
    ON u.approval_role_id = ar.approval_role_id
WHERE u.is_active = 1;

-- 2. Supplier master data
SELECT
    s.supplier_id,
    s.supplier_name,
    s.category,
    s.status
FROM suppliers s
WHERE s.status IN ('active', 'blocked');

-- 3. Approval matrix
SELECT
    approval_role,
    approval_limit
FROM approval_matrix
WHERE effective_from <= :period_to
  AND COALESCE(effective_to, '9999-12-31') >= :period_from;

-- 4. Purchase orders
SELECT
    po.po_id,
    po.created_date,
    po.supplier_id,
    po.requester_user_id,
    po.buyer_user_id,
    po.amount,
    po.category,
    po.status,
    po.release_date
FROM purchase_orders po
WHERE po.created_date >= :period_from
  AND po.created_date < :period_to;

-- 5. Approval workflow
SELECT
    aw.po_id,
    aw.approval_date,
    aw.approver_user_id,
    aw.required_approval_role,
    aw.amount,
    aw.approval_status
FROM approval_workflow aw
WHERE aw.po_created_date >= :period_from
  AND aw.po_created_date < :period_to;

-- 6. Goods receipts
SELECT
    gr.gr_id,
    gr.po_id,
    gr.receipt_date,
    gr.received_amount,
    gr.status
FROM goods_receipts gr
WHERE gr.receipt_date >= :period_from
  AND gr.receipt_date < DATEADD(day, 45, :period_to);

-- 7. Invoices
SELECT
    i.invoice_id,
    i.invoice_number,
    i.supplier_id,
    i.po_id,
    i.invoice_date,
    i.amount,
    i.status
FROM invoices i
WHERE i.invoice_date >= :period_from
  AND i.invoice_date < DATEADD(day, 45, :period_to);

-- 8. Payments
SELECT
    p.payment_id,
    p.invoice_id,
    p.supplier_id,
    p.payment_date,
    p.amount,
    p.status
FROM payments p
WHERE p.payment_date >= :period_from
  AND p.payment_date < DATEADD(day, 60, :period_to);
