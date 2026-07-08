# Procurement Process Regulation

**Organization:** Lanninster-Soprano Joint Company (LSJC)  
**Document owner:** Procurement Department  
**Version:** 2025.3  
**Effective from:** 2025-11-01  
**Status:** Synthetic document for AuditFlow example  

---

## 1. Purpose

This regulation describes the standard purchase-to-pay process for Lanninster-Soprano Joint Company (LSJC).

The process covers:

- purchase request initiation;
- purchase order creation;
- purchase order approval;
- purchase order release to supplier;
- goods receipt;
- invoice processing;
- payment approval.

This document is intentionally imperfect for the synthetic audit example. Some controls are clearly described, some controls are described weakly, and some expected controls are not described at all.

This reflects what auditors often see in real work: the regulation is useful, but it does not fully prove that the process is controlled.

---

## 2. Roles

### Requester

The requester initiates the business need and provides purchase justification.

### Buyer

The buyer creates the purchase order in the ERP system and checks that supplier, item, quantity, and amount are reasonable.

### Approver

The approver reviews and approves purchase orders according to the approval authority matrix.

### Accounts Payable Specialist

The AP specialist processes supplier invoices and prepares them for payment.

### Treasury

Treasury releases approved payment batches.

### ERP Product Owner

The ERP Product Owner maintains workflow configuration and user roles.

---

## 3. Purchase Order Creation

Purchase orders must be created in the ERP system before commitment to a supplier, except for emergency purchases.

Each purchase order should include:

- supplier;
- requester;
- buyer;
- purchase category;
- amount;
- business justification;
- expected delivery or service date.

Emergency purchases must be documented after the fact.

**Control gap intentionally retained:**  
This regulation does not define clear criteria for emergency purchases or require periodic review of emergency purchase usage.

---

## 4. Purchase Order Approval

Purchase orders must be approved before release to suppliers.

Approval limits are defined in the approval authority matrix:

| Approval role | Approval limit |
|---|---:|
| Buyer | 10,000 |
| Manager | 100,000 |
| Director | 250,000 |
| CFO | Unlimited |

The ERP workflow should route purchase orders to an approver with sufficient approval authority.

### C-001 — Purchase order release after approval

**Expected control:** Purchase orders should not be released to suppliers before required approval is completed.

**Control type:** Preventive  
**Control nature:** Application / workflow  
**Risk addressed:** Unauthorized purchases  

The system is expected to block release of unapproved purchase orders.

### C-002 — Approval authority check

**Expected control:** Purchase orders should be approved by users with sufficient approval authority.

**Control type:** Preventive  
**Control nature:** Application / workflow  
**Risk addressed:** Unauthorized purchases  

The ERP workflow should compare purchase order amount with the approver's approval role.

---

## 5. Invoice Processing

Supplier invoices are recorded by Accounts Payable.

AP should verify that:

- the supplier exists in the ERP system;
- the invoice relates to a valid purchase order;
- the invoice amount appears reasonable;
- the invoice has not already been paid.

### C-003 — Duplicate invoice review

**Expected activity:** AP specialists should check whether the same invoice number has already been processed for the same supplier.

**Control type:** Detective  
**Control nature:** Manual  
**Risk addressed:** Duplicate payments  

**Design limitation intentionally retained:**  
The regulation does not define how the duplicate review should be performed, what fields should be compared, whether similar invoice numbers should be considered, or whether the ERP system blocks duplicate invoice numbers.

This is a weakly designed control. It may not be suitable for operating effectiveness testing without further clarification.

---

## 6. Payment Processing

Payment batches are prepared by Accounts Payable and released by Treasury.

Payment batches should be based on approved and posted invoices.

Treasury should release only payment batches prepared through the standard ERP workflow.

---

## 7. Goods Receipt

Goods receipt should be recorded before invoice payment for goods-based purchases.

For services, confirmation of service acceptance may be used instead of goods receipt.

**Design limitation intentionally retained:**  
This regulation does not clearly define how service acceptance should be recorded or how AP should distinguish service invoices from goods invoices when checking receipt evidence.

This area may require separate audit attention, but it is not part of the current synthetic audit scope.

---

## 8. Purchase Splitting

The regulation does not explicitly describe a control to prevent or detect splitting purchases into smaller transactions below approval thresholds.

There is no defined periodic review of:

- multiple purchase orders to the same supplier;
- repeated purchase orders created by the same requester;
- purchases close to approval thresholds;
- purchases with similar descriptions over a short period.

**Control gap intentionally retained:**  
The absence of a purchase splitting review is relevant to audit planning. The audit team may use data analysis to identify red flags, but there is no formal control design to test.

---

## 9. Management Monitoring

Procurement management reviews monthly spend reports.

The regulation does not specify whether these reports include:

- unapproved purchase orders;
- purchase orders released before approval;
- duplicate invoice indicators;
- split purchase indicators;
- override usage;
- emergency purchases.

---
