"""Prompt template. The parser fills {{email}} and {{report}} and sends it to Sonnet."""

PROMPT = """You are extracting unsolved tickets from a bug report and an evaluator email.

Read both sources. The email clarifies the report. Where they disagree, follow the email.

Return only a JSON array of the tickets that are still unsolved. Do not include tickets the sources mark as fixed or closed. Do not invent tickets.

Each object needs enough context and clarity for someone else to pick the ticket up without rereading the report:
- id
- title
- severity
- report_status: the report's own label only (for example Open, Partially Fixed). Do not set workflow status.
- kind: "new" or "recurrent". Use "new" when this ticket is a first report. Use "recurrent" when the report says the same defect returned, failed a retest, or is the same behaviour as an earlier ticket.
- kind_reason: one sentence citing how the report or email supports that kind
- services: the product areas this ticket touches. Use names from PRODUCT AREAS when the report or email matches them. If the source does not identify a service, use an empty list.
- context: what is still wrong, what the retest showed, and any clarification from the email
- expected

Do not propose a next step, a fix, or how another agent should handle the ticket. Report the defect only.

PRODUCT AREAS
{{code_context}}

EVALUATOR EMAIL
{{email}}

BUG REPORT
{{report}}
"""
