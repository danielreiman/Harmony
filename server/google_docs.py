from google.oauth2 import service_account
from googleapiclient.discovery import build


DOC_SCOPE = "https://www.googleapis.com/auth/documents"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


def _extract_doc_id(raw):
    """Strips a Google Docs URL down to just the document ID."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("doc_id is required")
    if "docs.google.com" in raw and "/d/" in raw:
        return raw.split("/d/", 1)[1].split("/", 1)[0]
    return raw


def _scan_text_runs(document):
    """Walks every text run in the document body and returns the full plain text plus char-to-doc-index segments used for anchor resolution."""
    body = document.get("body") or {}
    content_blocks = body.get("content") or []

    text_parts = []
    segments = []
    cursor = 0

    for block in content_blocks:
        paragraph = block.get("paragraph") or {}
        elements = paragraph.get("elements") or []
        for element in elements:
            run = element.get("textRun") or {}
            text = run.get("content") or ""
            doc_index = element.get("startIndex")
            if text and doc_index is not None:
                text_parts.append(text)
                segment = (cursor, cursor + len(text), int(doc_index))
                segments.append(segment)
                cursor = cursor + len(text)

    full_text = "".join(text_parts)
    return full_text, segments


def _find_anchor_range(document, anchor_text):
    """Locates anchor_text in the document and returns its (start, end) doc indices so the caller knows where to insert relative to it."""
    full_text, segments = _scan_text_runs(document)
    anchor = anchor_text.strip()
    position = full_text.lower().find(anchor.lower())
    if position == -1:
        return None

    def flat_to_doc(char_index):
        for seg_start, seg_end, doc_start in segments:
            if seg_start <= char_index < seg_end:
                return doc_start + (char_index - seg_start)
        return None

    start = flat_to_doc(position)
    end = flat_to_doc(position + len(anchor) - 1)

    if start is None or end is None:
        return None

    return start, end + 1


class DocManager:
    def __init__(self, service_account_file):
        """Connects to Google Docs using the service account so agents can read and write documents."""
        if not service_account_file:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE is missing")
        creds = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=[DOC_SCOPE, DRIVE_SCOPE]
        )
        self.client = build("docs", "v1", credentials=creds, cache_discovery=False)

    def _fetch_document(self, doc_id):
        """Downloads the raw document object from Google Docs."""
        return self.client.documents().get(documentId=_extract_doc_id(doc_id)).execute()

    def _batch_update(self, doc_id, requests):
        """Sends a list of write operations to Google Docs and returns the API replies."""
        response = self.client.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()
        return response.get("replies", [])

    def read(self, doc_id):
        """Fetches the document and returns its plain text — agents call this before writing to check existing content."""
        target = _extract_doc_id(doc_id)
        text, _ = _scan_text_runs(self._fetch_document(target))
        return {"doc_id": target, "text": text.strip()}

    def write(self, doc_id, payload, index=None, dedupe=True):
        """Writes text or raw API requests to the document, with optional anchor positioning and duplicate detection."""
        target = _extract_doc_id(doc_id)

        if isinstance(payload, dict):
            raw_requests = payload.get("requests") or payload.get("ops")
            if raw_requests:
                replies = self._batch_update(target, raw_requests)
                return {"doc_id": target, "written": 0, "replies": replies}

            text = payload.get("text", "") or ""
            index = payload.get("index", index)
            dedupe = payload.get("dedupe", dedupe)
            text_style = payload.get("text_style")
            paragraph_style = payload.get("paragraph_style")
            text_fields = payload.get("text_fields")
            paragraph_fields = payload.get("paragraph_fields")
            bullet_preset = payload.get("bullet_preset")

            anchor = payload.get("anchor_text")
            if not anchor:
                anchor = payload.get("after_text")
            if not anchor:
                anchor = payload.get("before_text")
            if not anchor:
                anchor = payload.get("replace_text")

            anchor_mode = payload.get("anchor_mode")
            if not anchor_mode:
                if payload.get("before_text"):
                    anchor_mode = "before"
                elif payload.get("replace_text"):
                    anchor_mode = "replace"
                else:
                    anchor_mode = "after"
        else:
            if payload is None:
                text = ""
            else:
                text = str(payload)
            text_style = None
            paragraph_style = None
            text_fields = None
            paragraph_fields = None
            bullet_preset = None
            anchor = None
            anchor_mode = None

        if not text or not text.strip():
            raise ValueError("write_doc called with empty text")

        document = self._fetch_document(target)

        if dedupe:
            existing_text, _ = _scan_text_runs(document)
            normalized_new = " ".join(text.split()).lower()
            normalized_existing = " ".join(existing_text.split()).lower()
            if normalized_new and normalized_new in normalized_existing:
                return {"doc_id": target, "written": 0, "skipped": True, "reason": "duplicate"}

        pre_requests = []
        if anchor:
            anchor_range = _find_anchor_range(document, anchor)
            if anchor_range:
                anchor_start, anchor_end = anchor_range
                if anchor_mode == "before":
                    index = anchor_start
                elif anchor_mode == "replace":
                    delete_request = {"deleteContentRange": {"range": {"startIndex": anchor_start, "endIndex": anchor_end}}}
                    pre_requests.append(delete_request)
                    index = anchor_start
                else:
                    index = anchor_end

        blocks = (document.get("body") or {}).get("content") or []
        if blocks:
            doc_end = max(1, int(blocks[-1].get("endIndex", 1)))
        else:
            doc_end = 1

        if index is not None:
            insert_at = max(1, int(index))
        else:
            insert_at = max(1, doc_end - 1)

        text_to_insert = text if text.endswith("\n") else text + "\n"
        write_range = {"startIndex": insert_at, "endIndex": insert_at + len(text_to_insert)}

        all_requests = list(pre_requests)
        all_requests.append({"insertText": {"location": {"index": insert_at}, "text": text_to_insert}})

        if paragraph_style:
            all_requests.append({"updateParagraphStyle": {
                "range": write_range,
                "paragraphStyle": paragraph_style,
                "fields": paragraph_fields or ",".join(paragraph_style.keys()),
            }})

        if text_style:
            all_requests.append({"updateTextStyle": {
                "range": write_range,
                "textStyle": text_style,
                "fields": text_fields or ",".join(text_style.keys()),
            }})

        if bullet_preset:
            all_requests.append({"createParagraphBullets": {
                "range": write_range,
                "bulletPreset": bullet_preset,
            }})

        replies = self._batch_update(target, all_requests)
        return {"doc_id": target, "written": len(text), "skipped": False, "replies": replies}
