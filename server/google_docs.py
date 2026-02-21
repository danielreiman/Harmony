from typing import Any, Dict, List, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build


DOC_SCOPE = "https://www.googleapis.com/auth/documents"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


class DocManager:
    def __init__(self, service_account_file: str):
        if not service_account_file:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE is missing")

        scopes = [DOC_SCOPE, DRIVE_SCOPE]
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=scopes,
        )
        self.client = build("docs", "v1", credentials=credentials, cache_discovery=False)

    def _parse_doc_id(self, raw: str) -> str:
        if not raw or not raw.strip():
            raise ValueError("doc_id is required")

        cleaned = raw.strip()
        url_contains_doc_id_segment = "docs.google.com" in cleaned and "/d/" in cleaned

        if url_contains_doc_id_segment:
            parts = cleaned.split("/d/", 1)[1].split("/", 1)
            return parts[0]

        return cleaned

    def _fetch_doc(self, doc_id: str) -> Dict[str, Any]:
        target = self._parse_doc_id(doc_id)
        return self.client.documents().get(documentId=target).execute()

    def _build_text_map(self, document: Dict[str, Any]) -> Tuple[str, List[Tuple[int, int, int]]]:
        body = document.get("body", {}) or {}
        blocks = body.get("content", []) or []
        combined: List[str] = []
        segments: List[Tuple[int, int, int]] = []

        char_pos = 0
        for block in blocks:
            paragraph = block.get("paragraph")
            if not paragraph:
                continue
            elements = paragraph.get("elements", []) or []
            for element in elements:
                text_span = element.get("textRun")
                if not text_span:
                    continue
                content = text_span.get("content") or ""
                start_index = element.get("startIndex")
                if start_index is None:
                    continue
                combined.append(content)
                seg_len = len(content)
                segments.append((char_pos, char_pos + seg_len, int(start_index)))
                char_pos += seg_len

        return "".join(combined), segments

    def _find_anchor_range(self, document: Dict[str, Any], anchor_text: Optional[str]) -> Optional[Tuple[int, int]]:
        if not anchor_text:
            return None

        combined, segments = self._build_text_map(document)
        if not combined:
            return None

        anchor = anchor_text.strip()
        if not anchor:
            return None

        anchor_position = combined.lower().find(anchor.lower())
        if anchor_position == -1:
            return None

        def char_to_doc(char_idx: int) -> Optional[int]:
            for c_start, c_end, doc_start in segments:
                if c_start <= char_idx < c_end:
                    return doc_start + (char_idx - c_start)
            return None

        start_doc = char_to_doc(anchor_position)
        end_doc = char_to_doc(anchor_position + len(anchor) - 1)

        if start_doc is None or end_doc is None:
            return None

        return start_doc, end_doc + 1

    def _extract_text(self, document: Dict[str, Any]) -> str:
        body = document.get("body", {}) or {}
        blocks = body.get("content", []) or []

        chunks = []
        for block in blocks:
            paragraph = block.get("paragraph")
            if not paragraph:
                continue
            elements = paragraph.get("elements", []) or []
            for element in elements:
                text_span = element.get("textRun")
                if not text_span:
                    continue
                content = text_span.get("content")
                if content:
                    chunks.append(content)

        return "".join(chunks).strip()

    def _end_index(self, document: Dict[str, Any]) -> int:
        body = document.get("body", {}) or {}
        blocks = body.get("content", []) or []
        if not blocks:
            return 1
        last_block = blocks[-1]
        return max(1, int(last_block.get("endIndex", 1)))

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.split()).strip().lower()

    def read(self, doc_id: str) -> Dict[str, Any]:
        target = self._parse_doc_id(doc_id)
        document = self._fetch_doc(target)
        full_text = self._extract_text(document)
        return {"doc_id": target, "text": full_text}

    def _apply_requests(self, doc_id: str, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not requests:
            raise ValueError("No requests provided for batchUpdate")

        response = self.client.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()
        return {"doc_id": doc_id, "written": 0, "replies": response.get("replies", [])}

    def _insert_text_requests(
        self,
        document: Dict[str, Any],
        text: str,
        index: Optional[int],
        text_style: Optional[Dict[str, Any]],
        paragraph_style: Optional[Dict[str, Any]],
        text_fields: Optional[str],
        paragraph_fields: Optional[str],
        bullet_preset: Optional[str],
        pre_requests: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        end_index = self._end_index(document)
        insert_at = max(1, int(index)) if index is not None else max(1, end_index - 1)

        text_to_insert = text if text.endswith("\n") else text + "\n"
        start = insert_at
        end = insert_at + len(text_to_insert)

        requests: List[Dict[str, Any]] = []

        if pre_requests:
            requests.extend(pre_requests)

        requests.append(
            {
                "insertText": {
                    "location": {"index": insert_at},
                    "text": text_to_insert,
                }
            }
        )

        if paragraph_style:
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "paragraphStyle": paragraph_style,
                        "fields": paragraph_fields or ",".join(paragraph_style.keys()),
                    }
                }
            )

        if text_style:
            requests.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": text_style,
                        "fields": text_fields or ",".join(text_style.keys()),
                    }
                }
            )

        if bullet_preset:
            requests.append(
                {
                    "createParagraphBullets": {
                        "range": {"startIndex": start, "endIndex": end},
                        "bulletPreset": bullet_preset,
                    }
                }
            )

        return requests

    def write(
        self,
        doc_id: str,
        payload: Any,
        index: Optional[int] = None,
        dedupe: Optional[bool] = True,
    ) -> Dict[str, Any]:
        target = self._parse_doc_id(doc_id)

        if isinstance(payload, dict):
            requests = payload.get("requests") or payload.get("ops")
            text = payload.get("text", "") or ""
            index = payload.get("index", index)
            text_style = payload.get("text_style")
            paragraph_style = payload.get("paragraph_style")
            text_fields = payload.get("text_fields")
            paragraph_fields = payload.get("paragraph_fields")
            bullet_preset = payload.get("bullet_preset")
            dedupe = payload.get("dedupe", dedupe)

            anchor_text = (
                payload.get("anchor_text")
                or payload.get("after_text")
                or payload.get("before_text")
                or payload.get("replace_text")
            )

            anchor_mode = payload.get("anchor_mode")
            if not anchor_mode:
                if payload.get("before_text"):
                    anchor_mode = "before"
                elif payload.get("replace_text"):
                    anchor_mode = "replace"
                else:
                    anchor_mode = "after"
        else:
            requests = None
            text = "" if payload is None else str(payload)
            text_style = None
            paragraph_style = None
            text_fields = None
            paragraph_fields = None
            bullet_preset = None
            anchor_text = None
            anchor_mode = None

        if requests:
            return self._apply_requests(target, requests)

        text_is_empty = not text or not str(text).strip()
        if text_is_empty:
            raise ValueError("write_doc called with empty text")

        document = self._fetch_doc(target)

        if dedupe:
            existing_text = self._extract_text(document)
            norm_new = self._normalize_text(text)
            norm_existing = self._normalize_text(existing_text)
            text_already_exists = norm_new and norm_new in norm_existing
            if text_already_exists:
                return {"doc_id": target, "written": 0, "skipped": True, "reason": "duplicate"}

        pre_requests: List[Dict[str, Any]] = []

        if anchor_text:
            anchor_range = self._find_anchor_range(document, anchor_text)
            if anchor_range:
                anchor_start, anchor_end = anchor_range
                if anchor_mode == "before":
                    index = anchor_start
                elif anchor_mode == "replace":
                    pre_requests.append(
                        {"deleteContentRange": {"range": {"startIndex": anchor_start, "endIndex": anchor_end}}}
                    )
                    index = anchor_start
                else:
                    index = anchor_end

        batch_requests = self._insert_text_requests(
            document=document,
            text=text,
            index=index,
            text_style=text_style,
            paragraph_style=paragraph_style,
            text_fields=text_fields,
            paragraph_fields=paragraph_fields,
            bullet_preset=bullet_preset,
            pre_requests=pre_requests,
        )

        response = self.client.documents().batchUpdate(
            documentId=target,
            body={"requests": batch_requests},
        ).execute()

        return {
            "doc_id": target,
            "written": len(text),
            "skipped": False,
            "replies": response.get("replies", []),
        }
