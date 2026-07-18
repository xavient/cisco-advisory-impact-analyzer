# Business Requirements Document (BRD): [PRODUCT / FEATURE NAME]

<!--
  HOW TO USE THIS TEMPLATE
  - Fill every [PLACEHOLDER]. Delete any section that genuinely does not apply
    (remove it entirely — don't leave "N/A").
  - Stay focused on WHAT the business needs and WHY. Avoid HOW it will be built
    (no tech stack, code structure, or API design) — that is decided later in
    /speckit-plan. Product surface (commands, files a user sees, outputs) is
    fair game; internal implementation is not.
  - This document is written to be fed to `/speckit-specify` as the feature
    description. Section 6 (User Journeys) maps directly to the prioritized,
    independently-testable user stories in the resulting spec — write those
    with the most care.
  - HTML comments like this one are guidance and SHOULD be deleted as you fill
    each section.
-->

## Document Control

| Field             | Value                                                        |
| ----------------- | ------------------------------------------------------------ |
| BRD ID            | [e.g., BRD-001]                                              |
| Title             | [Product / feature name]                                     |
| Author            | [Name / team]                                                |
| Status            | [Draft \| In Review \| Approved]                            |
| Version           | [0.1.0]                                                      |
| Created           | [YYYY-MM-DD]                                                 |
| Last updated      | [YYYY-MM-DD]                                                 |
| Related documents | [links: one-pager, constitution, related BRDs/specs, tickets] |

## 1. Executive Summary

<!-- 2-4 sentences a busy stakeholder can read and immediately "get it":
     what this is, who it is for, and what outcome it creates. -->

[Summary]

## 2. Business Context & Problem Statement

<!-- The WHY. What is broken, missing, or costly today? Who feels the pain, and
     how much does it cost (time, money, risk, quality)? Quantify where you can. -->

[Context and problem]

## 3. Business Objectives & Goals

<!-- The outcomes this must achieve, stated as goals (not features). Prefer
     measurable goals. These set the direction; Section 8 makes them measurable. -->

- **G1** — [objective]
- **G2** — [objective]

## 4. Stakeholders & Users

| Stakeholder / user | Role in this product | What they need from it |
| ------------------ | -------------------- | ---------------------- |
| [role]             | [primary / reviewer / downstream / indirect] | [need] |

## 5. Scope

### 5.1 In Scope

- [capability or responsibility this product owns]

### 5.2 Out of Scope

<!-- As important as in-scope. Explicitly name things a reader might ASSUME are
     included but are not, and (briefly) who/what owns them instead. -->

- [explicitly excluded item — and where that responsibility lives, if anywhere]

## 6. User Journeys *(feeds the spec's prioritized user stories)*

<!-- Each journey must be INDEPENDENTLY VALUABLE and TESTABLE: if only this one
     shipped, would it deliver value on its own? Order by priority (P1 = most
     critical / the MVP slice). For each, give the actor, trigger, outcome, the
     step-by-step flow, and Given/When/Then acceptance. -->

### Journey 1 — [Title] (Priority: P1)

- **Actor:** [who]
- **Trigger:** [what starts it]
- **Outcome / value:** [what they get; why it matters]
- **Flow:**
  1. [step]
- **Acceptance:**
  - **Given** [state], **When** [action], **Then** [observable outcome]

### Journey 2 — [Title] (Priority: P2)

- **Actor:** [who]
- **Trigger:** [what starts it]
- **Outcome / value:** [what they get]
- **Flow:**
  1. [step]
- **Acceptance:**
  - **Given** [state], **When** [action], **Then** [observable outcome]

<!-- Add more journeys as needed, each with a priority. -->

## 7. Business Requirements

<!-- Capability-level requirements in business voice, each testable. Use
     MUST / SHOULD. Tag each with a priority. These become the FR-### items in
     the spec, so keep them unambiguous. -->

| ID    | Requirement                          | Priority |
| ----- | ------------------------------------ | -------- |
| BR-01 | The product MUST [capability]        | P1       |
| BR-02 | The product SHOULD [capability]      | P2       |

## 8. Success Metrics & Measurable Outcomes

<!-- Technology-agnostic, measurable, user/business focused. Avoid implementation
     metrics (no "API < 200ms", no framework/db specifics). -->

- **SC-01** — [measurable outcome]
- **SC-02** — [measurable outcome]

## 9. Assumptions

<!-- Reasonable defaults you are adopting so the spec doesn't have to ask. State
     them so they can be challenged. -->

- [assumption]

## 10. Constraints

<!-- Hard boundaries: standards/policies the product must obey, environmental
     limits, organizational rules. -->

- [constraint]

## 11. Dependencies

<!-- Other systems, agents, teams, or artifacts this relies on as input or hands
     off to as output. -->

- [dependency — input or output, and the direction]

## 12. Risks & Mitigations

| Risk   | Impact | Likelihood | Mitigation |
| ------ | ------ | ---------- | ---------- |
| [risk] | [H/M/L] | [H/M/L]   | [how it is reduced] |

## 13. Open Questions

<!-- Genuine unknowns for /speckit-specify or /speckit-clarify to resolve. Being
     honest here prevents the AI from guessing wrong. -->

- [question]

## 14. Glossary

| Term   | Definition   |
| ------ | ------------ |
| [term] | [definition] |
