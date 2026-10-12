"""S3 documents: the S1 sources plus the memo for the viewer; sources_only drops the memo."""

from jev.scenarios.s1_reconciliation.documents import load_s1_documents
from jev.scenarios.s3_citation_check.documents import MEMO_ID, load_s3_documents, sources_only
from tests.s1.facts import DATA


def test_the_memo_follows_the_unchanged_sources_and_is_dropped_for_the_pipelines() -> None:
    sources = load_s1_documents(DATA)
    docs = load_s3_documents(DATA)

    assert MEMO_ID not in [d.doc_id for d in sources.documents]
    assert docs.documents[:-1] == sources.documents
    assert docs.documents[-1].doc_id == MEMO_ID
    assert sources_only(docs) == sources
