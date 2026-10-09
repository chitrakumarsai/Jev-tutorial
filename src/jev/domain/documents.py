"""Source documents as loaded from disk."""

from pydantic import BaseModel, ConfigDict


class Document(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_id: str
    text: str


class DocumentSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    documents: tuple[Document, ...]

    def get(self, doc_id: str) -> Document:
        for document in self.documents:
            if document.doc_id == doc_id:
                return document
        raise KeyError(f"No document {doc_id!r}")
