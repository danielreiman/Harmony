from typing import Any, Dict

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
        if "docs.google.com" in cleaned and "/d/" in cleaned:
            parts = cleaned.split("/d/", 1)[1].split("/", 1)
            return parts[0]
        return cleaned

    def _fetch_doc(self, doc_id: str) -> Dict[str, Any]:
        target = self._parse_doc_id(doc_id)
        return self.client.documents().get(documentId=target).execute()

    def _end_index(self, document: Dict[str, Any]) -> int:
        body = document.get("body", {}) or {}
        blocks = body.get("content", []) or []
        if not blocks:
            return 1
        last_block = blocks[-1]
        return max(1, int(last_block.get("endIndex", 1)))

    def read(self, doc_id: str) -> Dict[str, Any]:
        target = self._parse_doc_id(doc_id)
        document = self._fetch_doc(target)
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

        full_text = "".join(chunks).strip()
        return {"doc_id": target, "text": full_text}

    def write(self, doc_id: str, text: str, index: int | None = None) -> Dict[str, Any]:
        if not text or not str(text).strip():
            raise ValueError("write_doc called with empty text")

        target = self._parse_doc_id(doc_id)
        document = self._fetch_doc(target)
        end_index = self._end_index(document)
        insert_at = max(1, int(index)) if index is not None else max(1, end_index - 1)

        text_to_insert = text if text.endswith("\n") else text + "\n"
        requests = [
            {
                "insertText": {
                    "location": {"index": insert_at},
                    "text": text_to_insert,
                }
            }
        ]

        response = self.client.documents().batchUpdate(
            documentId=target,
            body={"requests": requests},
        ).execute()
        return {"doc_id": target, "written": len(text), "replies": response.get("replies", [])}
