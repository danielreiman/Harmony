import datetime

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

    # --- Research formatting methods ---

    def create_outline(self, doc_id, title, sections):
        """Writes a professional research report outline into the doc with section placeholders."""
        target = _extract_doc_id(doc_id)
        document = self._fetch_document(target)

        blocks = (document.get("body") or {}).get("content") or []
        if blocks:
            insert_at = max(1, int(blocks[-1].get("endIndex", 1)) - 1)
        else:
            insert_at = 1

        date_str = datetime.datetime.now().strftime("%B %d, %Y")

        # Build the full outline text and track each region's offset and style.
        # style_regions: list of (start_offset, end_offset, named_style, text_style_dict)
        full_text = ""
        style_regions = []

        def add_block(text, named_style=None, bold=False, italic=False, grey=False, font_size=None):
            start = len(full_text)
            end = start + len(text)
            ts = {}
            if bold:
                ts["bold"] = bold
            if italic:
                ts["italic"] = italic
            if grey:
                ts["foregroundColor"] = {"color": {"rgbColor": {"red": 0.6, "green": 0.6, "blue": 0.6}}}
            if font_size:
                ts["fontSize"] = {"magnitude": font_size, "unit": "PT"}
            style_regions.append((start, end, named_style, ts))
            return text

        full_text += add_block(title + "\n", named_style="HEADING_1", bold=True)
        full_text += add_block("Generated: " + date_str + "\n\n", grey=True, font_size=10)

        for section in sections:
            full_text += add_block(section + "\n", named_style="HEADING_2", bold=True)
            full_text += add_block("⏳ Queued\n\n", italic=True, grey=True, font_size=10)

        full_text += add_block("Summary\n", named_style="HEADING_2", bold=True)
        full_text += add_block("⏳ Pending — written when all sections complete\n\n", italic=True, grey=True, font_size=10)

        full_text += add_block("Bibliography\n", named_style="HEADING_2", bold=True)
        full_text += add_block("⏳ Pending\n", italic=True, grey=True, font_size=10)

        # First batch: insert all text at once
        self._batch_update(target, [
            {"insertText": {"location": {"index": insert_at}, "text": full_text}}
        ])

        # Second batch: apply paragraph and text styles
        style_requests = []
        for start_offset, end_offset, named_style, ts in style_regions:
            abs_start = insert_at + start_offset
            abs_end = insert_at + end_offset
            r = {"startIndex": abs_start, "endIndex": abs_end}

            if named_style:
                style_requests.append({
                    "updateParagraphStyle": {
                        "range": r,
                        "paragraphStyle": {"namedStyleType": named_style},
                        "fields": "namedStyleType"
                    }
                })

            if ts:
                fields = []
                if "bold" in ts:
                    fields.append("bold")
                if "italic" in ts:
                    fields.append("italic")
                if "foregroundColor" in ts:
                    fields.append("foregroundColor")
                if "fontSize" in ts:
                    fields.append("fontSize")
                style_requests.append({
                    "updateTextStyle": {
                        "range": r,
                        "textStyle": ts,
                        "fields": ",".join(fields)
                    }
                })

        if style_requests:
            self._batch_update(target, style_requests)

    def update_placeholder(self, doc_id, section_label, status_text):
        """Replaces the ⏳ placeholder line under a section heading with a new status line."""
        target = _extract_doc_id(doc_id)
        document = self._fetch_document(target)

        placeholder_range = self._find_placeholder_after_heading(document, section_label)
        if placeholder_range is None:
            return

        placeholder_start, placeholder_end = placeholder_range

        # Choose color based on status
        if status_text.startswith("✓"):
            color = {"red": 0.22, "green": 0.47, "blue": 0.11}  # green
        else:
            color = {"red": 0.6, "green": 0.6, "blue": 0.6}  # grey

        new_line = status_text + "\n"

        requests = [
            {
                "deleteContentRange": {
                    "range": {"startIndex": placeholder_start, "endIndex": placeholder_end}
                }
            },
            {
                "insertText": {
                    "location": {"index": placeholder_start},
                    "text": new_line
                }
            },
            {
                "updateTextStyle": {
                    "range": {"startIndex": placeholder_start, "endIndex": placeholder_start + len(new_line)},
                    "textStyle": {
                        "italic": True,
                        "fontSize": {"magnitude": 9, "unit": "PT"},
                        "foregroundColor": {"color": {"rgbColor": color}}
                    },
                    "fields": "italic,fontSize,foregroundColor"
                }
            }
        ]
        self._batch_update(target, requests)

    def write_formatted_section(self, doc_id, section_label, body, sources, bibliography_entries, agent_id):
        """Replaces the ⏳ placeholder under a section heading with professional formatted findings."""
        target = _extract_doc_id(doc_id)
        document = self._fetch_document(target)

        placeholder_range = self._find_placeholder_after_heading(document, section_label)

        if placeholder_range is not None:
            placeholder_start, placeholder_end = placeholder_range
            # Delete the placeholder line first
            self._batch_update(target, [{
                "deleteContentRange": {
                    "range": {"startIndex": placeholder_start, "endIndex": placeholder_end}
                }
            }])
            # Re-fetch to get updated indices after deletion
            document = self._fetch_document(target)
            heading_range = _find_anchor_range(document, section_label)
            if heading_range:
                insert_at = heading_range[1]
            else:
                insert_at = placeholder_start
        else:
            # No placeholder found — append after heading
            document = self._fetch_document(target)
            heading_range = _find_anchor_range(document, section_label)
            if heading_range:
                insert_at = heading_range[1]
            else:
                blocks = (document.get("body") or {}).get("content") or []
                insert_at = max(1, int(blocks[-1].get("endIndex", 1)) - 1) if blocks else 1

        # Build replacement content: body + sources + status line
        full_text = ""
        style_regions = []  # (start_offset, end_offset, text_style_dict, is_link_url, link_url)

        def add_block(text, bold=False, italic=False, color=None, font_size=11, link_url=None):
            start = len(full_text)
            end = start + len(text)
            ts = {}
            if bold:
                ts["bold"] = bold
            if italic:
                ts["italic"] = italic
            if color:
                ts["foregroundColor"] = {"color": {"rgbColor": color}}
            ts["fontSize"] = {"magnitude": font_size, "unit": "PT"}
            if link_url:
                ts["link"] = {"url": link_url}
            style_regions.append((start, end, ts, bool(link_url), link_url))
            return text

        full_text += add_block(body.strip() + "\n\n", font_size=11)

        if sources:
            full_text += add_block("Sources:\n", bold=True, font_size=10)
            for source in sources:
                name = source.get("name", "")
                url = source.get("url", "")
                source_line = f"{name} — {url}\n"
                blue = {"red": 0.07, "green": 0.33, "blue": 0.80}
                full_text += add_block(source_line, color=blue, font_size=10, link_url=url if url else None)

        status_line = f"✓ Complete — {agent_id}\n\n"
        green = {"red": 0.22, "green": 0.47, "blue": 0.11}
        full_text += add_block(status_line, italic=True, color=green, font_size=9)

        # Insert all text at once
        self._batch_update(target, [
            {"insertText": {"location": {"index": insert_at}, "text": full_text}}
        ])

        # Apply styles in a second batch
        style_requests = []
        for start_offset, end_offset, ts, is_link, link_url in style_regions:
            abs_start = insert_at + start_offset
            abs_end = insert_at + end_offset
            r = {"startIndex": abs_start, "endIndex": abs_end}

            fields = []
            if "bold" in ts:
                fields.append("bold")
            if "italic" in ts:
                fields.append("italic")
            if "foregroundColor" in ts:
                fields.append("foregroundColor")
            if "fontSize" in ts:
                fields.append("fontSize")
            if "link" in ts:
                fields.append("link")

            if fields:
                style_requests.append({
                    "updateTextStyle": {
                        "range": r,
                        "textStyle": ts,
                        "fields": ",".join(fields)
                    }
                })

        # Make source lines into bullet points
        if sources:
            sources_label = "Sources:\n"
            sources_start_offset = len(body.strip() + "\n\n" + sources_label)
            sources_end_offset = sources_start_offset
            for source in sources:
                name = source.get("name", "")
                url = source.get("url", "")
                sources_end_offset += len(f"{name} — {url}\n")
            bullet_range = {
                "startIndex": insert_at + sources_start_offset,
                "endIndex": insert_at + sources_end_offset
            }
            style_requests.append({
                "createParagraphBullets": {
                    "range": bullet_range,
                    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
                }
            })

        if style_requests:
            self._batch_update(target, style_requests)

        return {"doc_id": target, "section": section_label, "written": len(full_text)}

    def write_summary(self, doc_id, text):
        """Replaces the ⏳ Pending placeholder under the Summary heading with the final summary text."""
        target = _extract_doc_id(doc_id)
        document = self._fetch_document(target)

        placeholder_range = self._find_placeholder_after_heading(document, "Summary")

        new_text = text.strip() + "\n\n"

        if placeholder_range is not None:
            placeholder_start, placeholder_end = placeholder_range
            requests = [
                {
                    "deleteContentRange": {
                        "range": {"startIndex": placeholder_start, "endIndex": placeholder_end}
                    }
                },
                {
                    "insertText": {
                        "location": {"index": placeholder_start},
                        "text": new_text
                    }
                },
                {
                    "updateTextStyle": {
                        "range": {"startIndex": placeholder_start, "endIndex": placeholder_start + len(new_text)},
                        "textStyle": {"fontSize": {"magnitude": 11, "unit": "PT"}},
                        "fields": "fontSize"
                    }
                }
            ]
            self._batch_update(target, requests)
        else:
            self.write(target, new_text, dedupe=False)

    def write_bibliography(self, doc_id, entries):
        """Replaces the ⏳ Pending placeholder under Bibliography with formatted, sorted citations."""
        target = _extract_doc_id(doc_id)
        document = self._fetch_document(target)

        placeholder_range = self._find_placeholder_after_heading(document, "Bibliography")

        # Sort alphabetically by author
        sorted_entries = sorted(entries, key=lambda e: (e.get("author") or "").lower())

        full_text = ""
        link_regions = []  # (start_offset, end_offset, url)

        for entry in sorted_entries:
            author = entry.get("author", "")
            year = entry.get("year", "n.d.")
            title = entry.get("title", "")
            source = entry.get("source", "")
            url = entry.get("url", "")

            citation_line = f"{author} ({year}). {title}. {source}.\n"
            full_text += citation_line

            if url:
                url_line = url + "\n"
                url_start = len(full_text)
                full_text += url_line
                link_regions.append((url_start, url_start + len(url_line), url))

            full_text += "\n"

        if not full_text:
            full_text = "No sources recorded.\n"

        if placeholder_range is not None:
            placeholder_start, placeholder_end = placeholder_range
            requests = [
                {
                    "deleteContentRange": {
                        "range": {"startIndex": placeholder_start, "endIndex": placeholder_end}
                    }
                },
                {
                    "insertText": {
                        "location": {"index": placeholder_start},
                        "text": full_text
                    }
                }
            ]
            self._batch_update(target, requests)

            # Apply URL link styles in a second batch
            blue = {"red": 0.07, "green": 0.33, "blue": 0.80}
            style_requests = []
            for start_offset, end_offset, url in link_regions:
                abs_start = placeholder_start + start_offset
                abs_end = placeholder_start + end_offset
                style_requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": abs_start, "endIndex": abs_end},
                        "textStyle": {
                            "link": {"url": url},
                            "foregroundColor": {"color": {"rgbColor": blue}},
                            "fontSize": {"magnitude": 10, "unit": "PT"}
                        },
                        "fields": "link,foregroundColor,fontSize"
                    }
                })

            if style_requests:
                self._batch_update(target, style_requests)
        else:
            self.write(target, full_text, dedupe=False)

    def _find_placeholder_after_heading(self, document, heading_text):
        """Finds the ⏳ status line that appears immediately after a section heading."""
        full_text, segments = _scan_text_runs(document)

        heading_pos = full_text.lower().find(heading_text.lower().strip())
        if heading_pos == -1:
            return None

        search_from = heading_pos + len(heading_text)
        placeholder_pos = full_text.find("⏳", search_from)
        if placeholder_pos == -1:
            return None

        # Make sure the placeholder is close to the heading (within 5 chars of newline after heading)
        between = full_text[search_from:placeholder_pos]
        if len(between) > 5:
            return None

        line_end = full_text.find("\n", placeholder_pos)
        if line_end == -1:
            line_end = len(full_text) - 1
        line_end_inclusive = line_end  # the \n character

        def flat_to_doc(char_index):
            for seg_start, seg_end, doc_start in segments:
                if seg_start <= char_index < seg_end:
                    return doc_start + (char_index - seg_start)
            return None

        start = flat_to_doc(placeholder_pos)
        end = flat_to_doc(line_end_inclusive)

        if start is None:
            return None

        if end is None:
            end = start + (line_end_inclusive - placeholder_pos)
        else:
            end += 1  # endIndex is exclusive in Google Docs API

        return start, end
