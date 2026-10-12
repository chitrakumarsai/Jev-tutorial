"""What present, partial and absent mean. Both sides get these exact words: Jev as its
status options, the LLM in its prompt (fairness: the same question, asked the same way)."""

from jev.domain.findings import ClauseVerdict

STATUS_DEFINITIONS: dict[ClauseVerdict, str] = {
    "present": "The addendum provides what the clause asks.",
    "partial": (
        "Related wording exists but does not do what the clause asks; "
        "related wording alone is not present."
    ),
    "absent": "Nothing in the addendum provides it.",
}
