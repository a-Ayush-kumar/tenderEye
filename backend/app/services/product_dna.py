"""Stub Product DNA / Evidence Locker.

Tracks document hashes in memory to detect duplicates across bids.
"""
import hashlib
from collections import defaultdict
from typing import Any, Dict


class _EvidenceLocker:
    def __init__(self) -> None:
        # tender_id -> list of dna records
        self._records: Dict[str, list] = defaultdict(list)
        # content_hash -> first doc_id seen
        self._hashes: Dict[str, str] = {}

    def register_document(
        self,
        doc_id: str,
        content: bytes,
        vendor_id: str,
        tender_id: str,
    ) -> dict:
        content_hash = hashlib.sha256(content or b"").hexdigest()
        is_duplicate = content_hash in self._hashes
        first_doc = self._hashes.get(content_hash)
        if not is_duplicate:
            self._hashes[content_hash] = doc_id

        record = {
            "doc_id": doc_id,
            "vendor_id": vendor_id,
            "tender_id": tender_id,
            "content_hash": content_hash,
            "is_duplicate": is_duplicate,
            "duplicate_of": first_doc if is_duplicate else None,
        }
        self._records[tender_id].append(record)
        return record

    def get_tender_dedup_report(self, tender_id: str) -> dict:
        records = self._records.get(tender_id, [])
        duplicates = [r for r in records if r["is_duplicate"]]
        return {
            "tender_id": tender_id,
            "total_documents": len(records),
            "duplicate_count": len(duplicates),
            "duplicates": duplicates,
        }


evidence_locker = _EvidenceLocker()
