# RAG Evaluation — Results

Generated 2026-09-22 02:22 by the Enterprise Knowledge Assistant.

Every answer below was produced through the HTTP API with no access to the
source documents beyond what retrieval returned. Answers are unedited.

## Setup

- **Corpus**: 10 documents, 55 chunks
- **Model**: `gemma-4-26b-a4b`
- **Embeddings**: `sentence-transformers` (384d, semantic)
- **Retrieval**: hybrid BM25 + vector, RRF fusion, top-k 6, coverage gate 0.2

---

## Level A — direct retrieval

### 1. What are NovaDesk's current business hours for non-P1 support?

Business hours are 09:00-18:00 Africa/Cairo, Sunday through Thursday, excluding Egyptian public holidays [1].

**Sources**

- `[1]` **01_customer_support_policy_2026.pdf**

<sub>Retrieved 6 passage(s) from: 01_customer_support_policy_2026.pdf, 05_novadesk_pro_product_manual_v4_2.pdf, 02_customer_support_policy_2025_SUPERSEDED.pdf, 03_enterprise_service_agreement_acme_2026.pdf</sub>

<sub>Status: grounded · 2.5s</sub>

### 2. What is the Enterprise Plus included monthly API volume for Acme Logistics Group?

The Enterprise Plus included API volume for Acme Logistics Group is 2,000,000 per calendar month [1].

**Sources**

- `[1]` **03_enterprise_service_agreement_acme_2026.pdf** — *Commercial Terms*

<sub>Retrieved 6 passage(s) from: 03_enterprise_service_agreement_acme_2026.pdf, 10_entity_reference.csv, 08_acme_account_usage_june_2026.pdf, 04_pricing_billing_guide_2026.pdf</sub>

<sub>Status: grounded · 0.8s</sub>

### 3. What is the current P1 initial response target?

The current P1 initial response target is 30 minutes, 24x7 [1].

**Sources**

- `[1]` **01_customer_support_policy_2026.pdf**

<sub>Retrieved 6 passage(s) from: 01_customer_support_policy_2026.pdf, 02_customer_support_policy_2025_SUPERSEDED.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 08_acme_account_usage_june_2026.pdf, 07_incident_INC_2026_041.pdf, 10_entity_reference.csv</sub>

<sub>Status: grounded · 1.4s</sub>

### 4. What is the production API path for creating a ticket?

The current production API base path is /v2 [3]. To create a ticket, the path is /v2/tickets/{id} [2].

**Sources**

- `[2]` **05_novadesk_pro_product_manual_v4_2.pdf** — *POST*
- `[3]` **05_novadesk_pro_product_manual_v4_2.pdf** — *Overview*

<sub>Retrieved 6 passage(s) from: 05_novadesk_pro_product_manual_v4_2.pdf, 04_pricing_billing_guide_2026.pdf</sub>

<sub>Status: grounded · 1.4s</sub>

### 5. What payment data is a support agent prohibited from sending to a general-purpose LLM?

Do not send full card numbers, authentication secrets, passwords, session cookies, or private cryptographic keys to a general-purpose LLM [1]. For AI debugging, you must never copy live access tokens into prompts [1].

**Sources**

- `[1]` **06_security_and_access_handbook_2026.pdf** — *Sensitive Data*

<sub>Retrieved 6 passage(s) from: 06_security_and_access_handbook_2026.pdf, 05_novadesk_pro_product_manual_v4_2.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 07_incident_INC_2026_041.pdf, 01_customer_support_policy_2026.pdf</sub>

<sub>Status: grounded · 1.3s</sub>

---

## Level B — multi-document retrieval

### 6. Acme has 2,184,600 API calls in June 2026. How many calls are billable overage, and what overage charge should the signed agreement produce?

There are 184,600 billable overage calls [3]. Based on the signed agreement, which includes a 2,000,000 included volume and an overage rate of USD 0.004 per API call above the included volume [2], the overage charge is USD 738.40 [3].

**Sources**

- `[2]` **03_enterprise_service_agreement_acme_2026.pdf** — *Commercial Terms*
- `[3]` **08_acme_account_usage_june_2026.pdf** — *Metric*

<sub>Retrieved 6 passage(s) from: 04_pricing_billing_guide_2026.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 08_acme_account_usage_june_2026.pdf, 10_entity_reference.csv</sub>

<sub>Status: grounded · 2.1s</sub>

### 7. For Acme, is a confirmed SLA outage compensated with a cash refund or a service credit? Cite the controlling agreement or policy.

For Acme, the remedy for SLA outages is a service credit rather than a cash refund [1]. The "03_enterprise_service_agreement_acme_2026.pdf" agreement controls when it conflicts with general support policy [1].

**Sources**

- `[1]` **03_enterprise_service_agreement_acme_2026.pdf** — *Support and Refund Interaction*

<sub>Retrieved 6 passage(s) from: 03_enterprise_service_agreement_acme_2026.pdf, 01_customer_support_policy_2026.pdf, 10_entity_reference.csv, 02_customer_support_policy_2025_SUPERSEDED.pdf</sub>

<sub>Status: grounded · 3.6s</sub>

### 8. A customer asks to reverse a duplicate charge for USD 700. What approvals or human review are required?

For a duplicate charge of USD 700, higher amounts above the normal approval threshold of USD 500 per customer per calendar month require Finance approval [1]. Additionally, human review is mandatory for requests involving more than USD 500 in cash refunds [1].

**Sources**

- `[1]` **01_customer_support_policy_2026.pdf**

<sub>Retrieved 6 passage(s) from: 01_customer_support_policy_2026.pdf, 04_pricing_billing_guide_2026.pdf, 07_incident_INC_2026_041.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 02_customer_support_policy_2025_SUPERSEDED.pdf</sub>

<sub>Status: grounded · 1.6s</sub>

### 9. A ticket says: I was charged twice, but one of the charges is still pending. What should support do differently from a confirmed duplicate capture?

Customer Support should distinguish duplicate authorization holds from confirmed duplicate charges before promising refunds [1]. For confirmed duplicate charges, support communications should state that they are being reversed, whereas pending authorization holds may disappear without a refund transaction [3].

**Sources**

- `[1]` **07_incident_INC_2026_041.pdf** — *Summary*
- `[3]` **07_incident_INC_2026_041.pdf** — *Resolution*

<sub>Retrieved 6 passage(s) from: 07_incident_INC_2026_041.pdf, 04_pricing_billing_guide_2026.pdf, 08_acme_account_usage_june_2026.pdf, 01_customer_support_policy_2026.pdf</sub>

<sub>Status: grounded · 1.3s</sub>

### 10. What information is missing from a ticket.created event if an AI agent needs the customer's billing history?

The `ticket.created` event does not contain the complete customer billing history; obtaining that information requires an authorized API call [1].

**Sources**

- `[1]` **05_novadesk_pro_product_manual_v4_2.pdf** — *Sample Event*

<sub>Retrieved 6 passage(s) from: 05_novadesk_pro_product_manual_v4_2.pdf, 09_internal_ai_governance_memo.docx, 06_security_and_access_handbook_2026.pdf</sub>

<sub>Status: grounded · 1.5s</sub>

---

## Level C — conflict and temporal reasoning

### 11. One document says P1 response is 1 hour and another says 30 minutes. Which should apply today, and why?

The 30-minute response time should apply because the 2026 policy, which is effective from 2026-06-01, defines the P1 initial response as "30 minutes, 24x7" [1][4]. The 1-hour target is found in a historical document that is "retained for audit purposes" and explicitly states, "Do not apply its thresholds to tickets governed by the 2026 policy" [2].

**Sources**

- `[1]` **01_customer_support_policy_2026.pdf**
- `[2]` **02_customer_support_policy_2025_SUPERSEDED.pdf** — *Historical Terms*
- `[4]` **01_customer_support_policy_2026.pdf**

<sub>Retrieved 6 passage(s) from: 01_customer_support_policy_2026.pdf, 02_customer_support_policy_2025_SUPERSEDED.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 05_novadesk_pro_product_manual_v4_2.pdf</sub>

<sub>Status: grounded · 3.4s</sub>

### 12. The 2025 policy says cash refunds above USD 250 need Finance approval, while the 2026 policy says USD 500. Which threshold should a current support workflow use?

The 2026 policy should be used, as the 2025 policy is a historical document that must not have its thresholds applied to tickets governed by the 2026 policy [1]. Under the 2026 policy, the normal approval threshold is USD 500 per customer per calendar month, and amounts higher than this require Finance approval [2].

**Sources**

- `[1]` **02_customer_support_policy_2025_SUPERSEDED.pdf** — *Historical Terms*
- `[2]` **01_customer_support_policy_2026.pdf**

<sub>Retrieved 6 passage(s) from: 02_customer_support_policy_2025_SUPERSEDED.pdf, 01_customer_support_policy_2026.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 08_acme_account_usage_june_2026.pdf, 04_pricing_billing_guide_2026.pdf</sub>

<sub>Status: grounded · 2.2s</sub>

### 13. Acme's June report shows a USD 480 service credit. Is that consistent with a 5% Enterprise Plus credit on a USD 4,800 platform fee? Explain any discrepancy.

No, it is not consistent, as 5% of the USD 4,800 platform fee is USD 240 [1]. The report shows USD 480 because "Finance applied two monthly-credit entries during the reconciliation period," which is described as a "deliberate discrepancy for the benchmark" [1].

**Sources**

- `[1]` **08_acme_account_usage_june_2026.pdf** — *Metric*

<sub>Retrieved 6 passage(s) from: 08_acme_account_usage_june_2026.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 04_pricing_billing_guide_2026.pdf</sub>

<sub>Status: grounded · 3.3s</sub>

### 14. If Acme asks for a cash refund because of an SLA outage, what should the AI agent tell the customer, and what should it avoid promising?

For SLA outages, the remedy is a service credit rather than a cash refund [1]. A support representative must not promise a cash refund when the customer agreement defines a service-credit remedy instead [2].

**Sources**

- `[1]` **03_enterprise_service_agreement_acme_2026.pdf** — *Support and Refund Interaction*
- `[2]` **01_customer_support_policy_2026.pdf**

<sub>Retrieved 6 passage(s) from: 03_enterprise_service_agreement_acme_2026.pdf, 01_customer_support_policy_2026.pdf, 09_internal_ai_governance_memo.docx, 07_incident_INC_2026_041.pdf, 10_entity_reference.csv, 02_customer_support_policy_2025_SUPERSEDED.pdf</sub>

<sub>Status: grounded · 2.8s</sub>

### 15. An AI agent wants to automatically send a reply about a possible security breach. What governance constraints apply?

AI-generated replies must not make unverified claims about breaches, refunds, or regulatory obligations [1]. AI must not autonomously disclose confidential incident details [3]. AI-generated draft replies may be sent automatically only when the ticket is low risk, no restricted category is detected, confidence is at least 0.90, and no human-review trigger is present [5]. Additionally, the product team does not recommend exposing raw LLM responses directly to customers without application-level validation [6].

**Sources**

- `[1]` **06_security_and_access_handbook_2026.pdf** — *Security Incident Procedure*
- `[3]` **09_internal_ai_governance_memo.docx** — *Restricted Use Cases*
- `[5]` **01_customer_support_policy_2026.pdf**
- `[6]` **05_novadesk_pro_product_manual_v4_2.pdf** — *AI Integration Pattern*

<sub>Retrieved 6 passage(s) from: 06_security_and_access_handbook_2026.pdf, 09_internal_ai_governance_memo.docx, 01_customer_support_policy_2026.pdf, 05_novadesk_pro_product_manual_v4_2.pdf</sub>

<sub>Status: grounded · 2.6s</sub>

---

## Level D — reasoning and synthesis

### 16. Which documents are needed to answer why Acme was billed an overage in June, what rate applies, and whether the service credit was calculated correctly?

To answer why Acme was billed an overage in June, the applicable rate, and the correctness of the service credit calculation, the following documents are needed:

*   **08_acme_account_usage_june_2026.pdf**: This document provides the June usage metrics, including 2,184,600 total API calls, 2,000,000 included calls, and 184,600 billable overage calls [2]; it also lists the contract overage rate as "USD 0.004/call" [2]; and it addresses the service credit discrepancy, noting that while the 5% uptime credit should be USD 240, the report shows USD 480 due to two monthly-credit entries applied by Finance [2].
*   **03_enterprise_service_agreement_acme_2026.pdf**: This document establishes the contractual overage rate of "USD 0.004 per API call above the included volume" [5] and defines the "Enterprise Plus" plan terms [5].
*   **04_pricing_billing_guide_2026.pdf**: This document explains the calculation method for usage overage, stating it is "calculated after included monthly volume is applied" [4].

**Sources**

- `[2]` **08_acme_account_usage_june_2026.pdf** — *Metric*
- `[4]` **04_pricing_billing_guide_2026.pdf** — *Invoice Construction*
- `[5]` **03_enterprise_service_agreement_acme_2026.pdf** — *Commercial Terms*

<sub>Retrieved 6 passage(s) from: 10_entity_reference.csv, 08_acme_account_usage_june_2026.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 04_pricing_billing_guide_2026.pdf, 02_customer_support_policy_2025_SUPERSEDED.pdf</sub>

<sub>Status: grounded · 7.4s</sub>

### 17. Given incident INC-2026-041, how should an AI support workflow distinguish a duplicate authorization hold from a confirmed duplicate charge?

Customer Support should distinguish duplicate authorization holds from confirmed duplicate charges before promising refunds [2]. Support communications should state that confirmed duplicate charges are being reversed and that pending authorization holds may disappear without a refund transaction [1]. Additionally, the support playbook should be updated with the distinction between an authorization hold and a captured charge [4].

**Sources**

- `[1]` **07_incident_INC_2026_041.pdf** — *Resolution*
- `[2]` **07_incident_INC_2026_041.pdf** — *Summary*
- `[4]` **07_incident_INC_2026_041.pdf** — *Follow-up Actions*

<sub>Retrieved 6 passage(s) from: 07_incident_INC_2026_041.pdf, 08_acme_account_usage_june_2026.pdf, 10_entity_reference.csv</sub>

<sub>Status: grounded · 1.7s</sub>

### 18. A support ticket from Acme is low confidence, requests a USD 900 refund, and mentions possible account takeover. Should the AI respond automatically? Explain using the applicable rules.

No, the AI should not respond automatically. According to the policy, AI-generated draft replies may only be sent automatically when the ticket is low risk, no restricted category is detected, confidence is at least 0.90, and no human-review trigger is present [1]. This specific case fails multiple requirements:

*   **Confidence:** The request is described as "low confidence," and the system must request more information or route the case to a human when AI confidence is below 0.75 [1, 3].
*   **Human Review Triggers:** Human review is mandatory for "account ownership disputes" and "any P1 incident" [1]. Additionally, "account takeover" is a security event that requires immediate escalation to Security Operations [2, 4].
*   **Refund Threshold:** The USD 900 request exceeds the normal approval threshold of "USD 500 per customer per calendar month," which requires Finance approval [1].

**Sources**

- `[1]` **01_customer_support_policy_2026.pdf**
- `[2]` **03_enterprise_service_agreement_acme_2026.pdf** — *Support and Refund Interaction*
- `[3]` **01_customer_support_policy_2026.pdf**
- `[4]` **06_security_and_access_handbook_2026.pdf** — *Security Incident Procedure*

<sub>Retrieved 6 passage(s) from: 01_customer_support_policy_2026.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 06_security_and_access_handbook_2026.pdf, 10_entity_reference.csv, 09_internal_ai_governance_memo.docx</sub>

<sub>Status: grounded · 6.9s</sub>

### 19. In the recommended architecture of validate, retrieve context, call LLM, validate response, apply business rules, persist, notify and escalate, which stages should be deterministic application logic rather than delegated to the LLM?

The provided documents do not specify which stages of the recommended architecture should be deterministic application logic rather than delegated to the LLM. The documents only state that the recommended architecture is "receive event -> validate payload -> optionally retrieve customer/order context -> call LLM with structured schema -> validate response -> apply business rules -> persist result -> notify or escalate" [1] and note that the product team "does not recommend exposing raw LLM responses directly to customers without application-level validation" [1].

**Sources**

- `[1]` **05_novadesk_pro_product_manual_v4_2.pdf** — *AI Integration Pattern*

<sub>Retrieved 6 passage(s) from: 05_novadesk_pro_product_manual_v4_2.pdf, 09_internal_ai_governance_memo.docx, 06_security_and_access_handbook_2026.pdf, 01_customer_support_policy_2026.pdf</sub>

<sub>Status: grounded · 2.6s</sub>

### 20. What is the strongest evidence that the AI system should avoid using the historical 2025 support policy for current SLA answers?

The 2026 NovaDesk Customer Support Policy "supersedes version 2.7 dated 2025-10-15" [2]. Additionally, the 2025 policy is explicitly labeled as "SUPERSEDED" [6].

**Sources**

- `[2]` **01_customer_support_policy_2026.pdf**
- `[6]` **02_customer_support_policy_2025_SUPERSEDED.pdf**

<sub>Retrieved 6 passage(s) from: 01_customer_support_policy_2026.pdf, 09_internal_ai_governance_memo.docx, 02_customer_support_policy_2025_SUPERSEDED.pdf</sub>

<sub>Status: grounded · 1.5s</sub>

---

## Level E — adversarial and citation quality

### 21. Which two sources could cause a naive RAG system to quote the wrong support policy, and how should metadata or reranking prevent that?

The two sources that could cause a naive RAG system to quote the wrong support policy are "01_customer_support_policy_2026.pdf" [1] and "02_customer_support_policy_2025_SUPERSEDED.pdf" [2], as the 2026 policy "supersedes version 2.7 dated 2025-10-15" [1]. The provided passages do not contain information regarding how metadata or reranking should prevent this.

**Sources**

- `[1]` **01_customer_support_policy_2026.pdf**
- `[2]` **02_customer_support_policy_2025_SUPERSEDED.pdf**

<sub>Retrieved 6 passage(s) from: 01_customer_support_policy_2026.pdf, 02_customer_support_policy_2025_SUPERSEDED.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 09_internal_ai_governance_memo.docx</sub>

<sub>Status: grounded · 3.0s</sub>

### 22. Is the USD 480 service credit in the June report necessarily proof that NovaDesk over-credited Acme? What additional reconciliation evidence would you request?

The USD 480 service credit is not necessarily proof of an error, as the report notes this is a "deliberate discrepancy for the benchmark" because Finance applied two monthly-credit entries during the reconciliation period [1]. While a 5% uptime credit under the Enterprise Plus agreement would normally be USD 240 (5% of USD 4,800), the report shows USD 480 due to these two entries [1].

Regarding additional reconciliation evidence, the documents indicate the June report was generated before the final finance reconciliation on 2026-07-05 [3].

**Sources**

- `[1]` **08_acme_account_usage_june_2026.pdf** — *Metric*
- `[3]` **08_acme_account_usage_june_2026.pdf** — *Support References*

<sub>Retrieved 6 passage(s) from: 08_acme_account_usage_june_2026.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 01_customer_support_policy_2026.pdf</sub>

<sub>Status: grounded · 5.3s</sub>

### 23. Can a support agent view a customer's full card number to validate a payment? What does the security handbook say?

No, payment data is masked except for the last four digits of a card where the role permits viewing it [2]. The security handbook also states that you must not send full card numbers to a general-purpose LLM [4].

**Sources**

- `[2]` **06_security_and_access_handbook_2026.pdf** — *Access Control*
- `[4]` **06_security_and_access_handbook_2026.pdf** — *Sensitive Data*

<sub>Retrieved 6 passage(s) from: 07_incident_INC_2026_041.pdf, 06_security_and_access_handbook_2026.pdf, 05_novadesk_pro_product_manual_v4_2.pdf, 08_acme_account_usage_june_2026.pdf</sub>

<sub>Status: grounded · 1.3s</sub>

### 24. A user asks the assistant to cancel an order and issue a USD 900 refund. Which parts require tool calls, which require deterministic business rules, and which require human approval?

Requests involving more than USD 500 in cash refunds require human review [1]. For any cash refund above USD 500, Finance approval is required under the general policy [2]. Regarding tool calls, automated actions with business impact must record the actor, timestamp, customer/tenant identifier, tool invoked, and outcome [3], and applications must record the model identifier, prompt/template version, tool calls, and a trace identifier for business-impacting AI actions [6]. Deterministic business rules are applied as part of the recommended architecture, which includes validating a response and applying business rules [4].

**Sources**

- `[1]` **01_customer_support_policy_2026.pdf**
- `[2]` **03_enterprise_service_agreement_acme_2026.pdf** — *Support and Refund Interaction*
- `[3]` **06_security_and_access_handbook_2026.pdf** — *Audit Requirements*
- `[4]` **05_novadesk_pro_product_manual_v4_2.pdf** — *AI Integration Pattern*
- `[6]` **09_internal_ai_governance_memo.docx** — *Model and Prompt Requirements*

<sub>Retrieved 6 passage(s) from: 01_customer_support_policy_2026.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 06_security_and_access_handbook_2026.pdf, 05_novadesk_pro_product_manual_v4_2.pdf, 09_internal_ai_governance_memo.docx</sub>

<sub>Status: grounded · 4.8s</sub>

### 25. Is the USD 480 service credit consistent with the 5% Enterprise Plus credit on the USD 4,800 platform fee? Give the answer, documents used, whether a conflict was detected, the calculation, and the recommended next step.

No, the USD 480 service credit is not consistent with a 5% credit of the USD 4,800 platform fee [1].

*   **Documents used:** 08_acme_account_usage_june_2026.pdf [1].
*   **Conflict detected:** Yes; the report shows USD 480, while 5% of the USD 4,800 platform fee is USD 240 [1].
*   **Calculation:** 5% of USD 4,800 = USD 240 [1].
*   **Recommended next step/Explanation:** The report states the USD 480 figure exists because "Finance applied two monthly-credit entries during the reconciliation period," noting this is a "deliberate discrepancy for the benchmark" [1].

**Sources**

- `[1]` **08_acme_account_usage_june_2026.pdf** — *Metric*

<sub>Retrieved 6 passage(s) from: 08_acme_account_usage_june_2026.pdf, 03_enterprise_service_agreement_acme_2026.pdf, 01_customer_support_policy_2026.pdf</sub>

<sub>Status: grounded · 6.5s</sub>

---

## Summary

| Outcome | Count |
|---|---|
| Grounded (all citations verified) | 25 |
| Answered but unverified | 0 |
| Refused (nothing retrieved) | 0 |
| **Total** | **25** |

A refusal is not necessarily a failure: for questions whose answer is not in
the corpus, refusing is the correct behaviour. Refusals on questions that
*are* answerable indicate a retrieval gap — with a lexical embedder, usually
a vocabulary mismatch between the question and the document.
