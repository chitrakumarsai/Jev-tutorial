"""Check the planted memo and the S3 key against the S1 documents before any model run."""

import re
from pathlib import Path

from jev.domain.documents import DocumentSet
from jev.extraction.text import find_quote
from jev.scenarios.s1_reconciliation.documents import load_s1_documents
from jev.scenarios.s3_citation_check.answer_key import S3KeyItem, load_s3_key
from jev.scenarios.s3_citation_check.documents import load_memo
from jev.scenarios.s3_citation_check.memo_draft import MemoCitation

_MSA_SECTION = re.compile(r"§(\d+\.\d+)")


def _in_cited_section(citation: MemoCitation, documents: DocumentSet) -> bool:
    """For an agreement citation ("§3.1"), whether the quote sits on that clause's line.
    Invoice citations ("L3") are located by their quote, so they count as correct."""
    match = _MSA_SECTION.fullmatch(citation.section.strip())
    if citation.doc_id != "msa" or match is None:
        return True
    clause = next(
        (line for line in documents.get("msa").text.split("\n") if line.startswith(match[1] + " ")),
        "",
    )
    single = DocumentSet.model_validate({"documents": [{"doc_id": "msa", "text": clause}]})
    return find_quote(single, citation.quote) is not None


def _check(item: S3KeyItem, citation: MemoCitation, documents: DocumentSet) -> list[str]:
    try:
        source = DocumentSet(documents=(documents.get(citation.doc_id),))
    except KeyError:
        return [f"{citation.id}: unknown document {citation.doc_id}"]
    found = find_quote(source, citation.quote) is not None
    if item.verdict == "fabricated":
        return [] if not found else [f"{citation.id}: keyed fabricated but its quote is real"]
    if not found:
        return [f"{citation.id}: quote not found in {citation.doc_id}"]
    in_section = _in_cited_section(citation, documents)
    if in_section != item.section_correct:
        return [
            f"{citation.id}: section_correct is {item.section_correct} but quote is "
            f"{'' if in_section else 'not '}in {citation.section}"
        ]
    return []


def validate_s3_data(data_dir: Path) -> list[str]:
    documents = load_s1_documents(data_dir)
    memo = load_memo(data_dir)
    key = {item.citation_id: item for item in load_s3_key(data_dir).items}
    problems = [
        f"{c.id}: in the memo but not in the answer key" for c in memo.citations if c.id not in key
    ]
    problems += [
        f"{cid}: in the key but not in the memo"
        for cid in key.keys() - {c.id for c in memo.citations}
    ]
    for citation in memo.citations:
        if citation.id in key:
            problems += _check(key[citation.id], citation, documents)
    return problems
