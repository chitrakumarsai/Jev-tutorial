"""How a source passage can relate to a memo claim. Both sides get these exact words: Jev as
its options, the LLM in its prompt (fairness: the same question, asked the same way)."""

from jev.domain.findings import CitationVerdict

RELATIONS: dict[str, str] = {
    "supports": "The passage states what the claim says.",
    "contradicts": "The passage states something that conflicts with the claim.",
    "says_nothing": "The passage neither states nor conflicts with what the claim says.",
}
RELATION_VERDICT: dict[str, CitationVerdict] = {
    "supports": "verified",
    "contradicts": "contradicted",
    "says_nothing": "unsupported",
}
