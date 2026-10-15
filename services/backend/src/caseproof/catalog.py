"""Sample policy and fictional fixture catalog (policies/). Expected outcomes live only in evaluation/."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from .config import APP_ROOT
from .pdfdocs import render_document

POLICY_PATH = APP_ROOT / "policies" / "sales-invoice-financing.v1.json"
CATALOG_PATH = APP_ROOT / "policies" / "fixtures" / "catalog.json"


@lru_cache
def sample_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text())


@lru_cache
def catalog() -> dict[str, Any]:
    data = json.loads(CATALOG_PATH.read_text())
    extra = os.environ.get("CASEPROOF_EXTRA_CATALOG")  # evaluation runner only; never set in a deployment
    if extra:
        more = json.loads(open(extra).read())
        data["parties"] = {**data["parties"], **more["parties"]}
        data["scenarios"] = data["scenarios"] + more["scenarios"]
    return data


def parties() -> dict[str, dict[str, str]]:
    return catalog()["parties"]


def scenario(key: str) -> dict[str, Any]:
    for item in catalog()["scenarios"]:
        if item["key"] == key:
            return item
    raise KeyError(key)


def scenarios() -> list[dict[str, Any]]:
    return catalog()["scenarios"]


def _documents_by_key() -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for sc in scenarios():
        for doc in sc["initial"]:
            docs[doc["key"]] = doc
        for staged in sc["staged"]:
            if staged.get("document") and staged["document"].get("spec"):
                docs[staged["document"]["key"]] = staged["document"]
    return docs


def fixture_bytes(doc: dict[str, Any]) -> bytes:
    """Render a fixture document. A copy renders the identical bytes of its original."""
    source = _documents_by_key()[doc.get("copy_of") or doc["key"]]
    return render_document(source["role"], source["spec"], parties())


def staged_response(scenario_key: str, staged_key: str) -> dict[str, Any]:
    for staged in scenario(scenario_key)["staged"]:
        if staged["key"] == staged_key:
            return staged
    raise KeyError(staged_key)
