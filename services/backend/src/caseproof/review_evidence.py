"""Validate model-proposed document relationships against the saved source passages."""

from __future__ import annotations

import re
import uuid
from collections import Counter

from pydantic import BaseModel, Field

from .history import record
from .models import Document, DocumentVersion
from .review_calculations import normalise


class Citation(BaseModel):
    source_label: str
    quote: str = Field(min_length=3, max_length=800)
    page: int | None = None


class ReplacementEvidence(BaseModel):
    document_reference: str = Field(min_length=1, max_length=200)
    notice: Citation = Field(description="Exact replacement declaration from the revised document.")
    original_identity: Citation = Field(description="Original document reference and party context.")
    replacement_identity: Citation = Field(
        description="The same document reference and party context in the revision."
    )


class ReplacementProposal(ReplacementEvidence):
    original_source: str
    replacement_source: str


def citation_supported(citation: dict, source: dict | None) -> bool:
    if not source or not (
        (source["active"] and source["state"] == "ready") or source.get("usage") == "comparison_only"
    ):
        return False
    text = source["text"]
    if citation.get("page") and source.get("pages"):
        text = next((p["text"] for p in source["pages"] if p["page"] == citation["page"]), "")
    quote = normalise(citation["quote"])
    return len(quote) >= 3 and quote in normalise(text)


def resolve_replacements(
    sources: list[dict], findings: dict, proposals: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Project explicit, cited replacements before validating the current calculations.

    Upload order and matching filenames never establish a replacement. Ambiguous
    forks/cycles stay unresolved; the normal evidence checks still apply to them.
    """
    by_label = {s["label"]: s for s in sources}
    counts = Counter((p["original_source"], p["replacement_source"]) for p in proposals)
    proofs = {
        (p["original_source"], p["replacement_source"]): p
        for p in proposals
        if counts[(p["original_source"], p["replacement_source"])] == 1
    }
    candidates = {}
    for finding in findings.values():
        for change in finding.get("changes", []):
            proof = proofs.get((change["original_source"], change["replacement_source"]))
            old = by_label.get(change["original_source"])
            new = by_label.get(change["replacement_source"])
            if (
                not proof
                or not old
                or not new
                or old["id"] == new["id"]
                or old["role"] != new["role"]
                or old["role"] not in {"invoice", "delivery_receipt"}
                or not all(
                    s["active"]
                    and s["state"] == "ready"
                    and not s.get("truncated")
                    and not s.get("reading_limitations")
                    for s in (old, new)
                )
                or new.get("replaces_source_id")
                or new.get("replaces_version")
                or change["result"] not in {"supported", "unchanged"}
            ):
                continue
            passages = [proof["original_identity"], proof["replacement_identity"], proof["notice"]]
            expected = [old, new, new]
            if not all(
                c["source_label"] == s["label"] and citation_supported(c, s)
                for c, s in zip(passages, expected, strict=True)
            ):
                continue
            reference = re.compile(
                r"(?<!\w)" + re.escape(normalise(proof["document_reference"])) + r"(?!\w)", re.I
            )
            if not all(reference.search(normalise(c["quote"])) for c in passages[:2]):
                continue
            candidates[(old["id"], new["id"])] = {
                "original_id": old["id"],
                "replacement_id": new["id"],
                "original_source": old["label"],
                "replacement_source": new["label"],
                "summary": change["summary"],
                "evidence": proof,
            }
    links = list(candidates.values())
    if not links:
        return sources, []
    outgoing = Counter(link["original_id"] for link in links)
    incoming = Counter(link["replacement_id"] for link in links)
    if any(n > 1 for n in [*outgoing.values(), *incoming.values()]):
        return sources, []
    ordered = []
    remaining = links[:]
    while remaining:
        children = {link["replacement_id"] for link in remaining}
        roots = [link for link in remaining if link["original_id"] not in children]
        if not roots:
            return sources, []
        ordered.extend(roots)
        remaining = [link for link in remaining if link not in roots]
    projected = {s["label"]: dict(s) for s in sources}
    for link in ordered:
        old, new = projected[link["original_source"]], projected[link["replacement_source"]]
        old.update(active=False, state="superseded", usage="comparison_only")
        new.update(
            document_id=old.get("document_id", old["id"]),
            version=(old.get("version") or 1) + 1,
            replaces_version=old.get("version") or 1,
            replaces_source_id=old["id"],
        )
        # These verified identity/declaration passages also support the final comparison.
        for finding in findings.values():
            if any(
                c["original_source"] == old["label"] and c["replacement_source"] == new["label"]
                for c in finding.get("changes", [])
            ):
                for key in ("original_identity", "replacement_identity", "notice"):
                    citation = link["evidence"][key]
                    if citation not in finding["citations"]:
                        finding["citations"].append(citation)
    return list(projected.values()), ordered


def commit_replacements(session, case, links: list[dict], actor) -> None:
    """Persist the verified projection in the same locked transaction as its review."""
    for link in links:
        old = session.get(DocumentVersion, uuid.UUID(link["original_id"]))
        new = session.get(DocumentVersion, uuid.UUID(link["replacement_id"]))
        if (
            not old
            or not new
            or any(v.case_id != case.id or not v.is_active or v.state != "ready" for v in (old, new))
            or old.source_role != new.source_role
        ):
            raise ValueError("Replacement sources changed before the review was saved.")
        if new.document_id != old.document_id:
            session.get(Document, new.document_id).active_version_id = None
        new.document_id = old.document_id
        new.version_no = (old.version_no or 1) + 1
        new.replaces_version_no = old.version_no or 1
        new.structured = {
            **(new.structured or {}),
            "replaces": str(old.id),
            "replacement_evidence": link["evidence"],
        }
        old.is_active, old.state = False, "superseded"
        session.get(Document, old.document_id).active_version_id = new.id
        record(
            session,
            case,
            "DocumentReplacementLinked",
            actor,
            f"{new.label} replaces {old.label}; the original is retained for comparison",
            reason=link["summary"],
            payload=link,
        )
    session.flush()
