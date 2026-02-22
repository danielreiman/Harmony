# Plan — Simplified Multi-Agent Research Mode

## The problem with research mode today

The AI is responsible for too many things at once:
- Controlling the desktop (clicking, typing, scrolling)
- Deciding when to call `read_doc` and `write_doc`
- Knowing the Google Docs API payload format (`paragraph_style`, `text_style`, `bullet_preset`)
- Tracking what it already wrote to avoid duplicates
- Managing a 5-step DOC FLOW sequence

This causes the agent to get stuck, write duplicates, skip sections, or spend most cycles re-reading the doc instead of researching. In a demo it is unpredictable.

---

## The fix: two clean phases

**Phase 1 — Browse.** The agent controls the desktop and collects information. It never touches the doc. It just browses, reads, and keeps going until it has enough.

**Phase 2 — Write.** When browsing is done, the *server* (not the AI) calls the AI once with a structured summarize prompt, gets back a JSON object with findings, sources, and bibliography — then the server formats it professionally and writes it to the doc using Google Docs API styles.

The AI does one thing at a time. It either browses or summarizes — never both.

---

## How it works end to end

### Example: one agent

**User submits:**
```
Task: "Research the impact of AI on healthcare"
Doc ID: 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
Research mode: on
```

**What happens:**

1. Manager finds one idle agent. Assigns the task directly. No splitting needed.

2. Agent browses: opens a browser, searches Google, opens articles, scrolls pages. Its conversation history fills up with screenshots and text it read on screen.

3. Agent's AI returns `"Next Action": null` — browsing is done.

4. Server calls `agent._extract_and_write()`:
   - Takes the last 20 messages from conversation history
   - Calls AI once with `RESEARCH_SUMMARIZE_PROMPT`
   - Gets back structured JSON:
     ```json
     {
       "title": "AI in Healthcare",
       "findings": [
         {
           "heading": "AI-Powered Diagnosis",
           "body": "DeepMind's retinal scan model detected over 50 eye conditions with 94% accuracy in clinical trials. Stanford's CheXNet reads chest X-rays more accurately than radiologists in pneumonia detection.",
           "sources": [
             {"name": "DeepMind Blog", "url": "https://deepmind.com/blog/ai-eye-disease"},
             {"name": "Stanford ML Group", "url": "https://stanfordmlgroup.github.io/projects/chexnet/"}
           ]
         }
       ],
       "summary": "AI in healthcare shows strong results in diagnosis and drug discovery...",
       "bibliography": [
         {"author": "De Fauw, J. et al.", "year": "2018", "title": "Clinically applicable deep learning for diagnosis", "source": "Nature Medicine", "url": "https://nature.com/articles/s41591-018-0107-6"},
         {"author": "Rajpurkar, P. et al.", "year": "2017", "title": "CheXNet: Radiologist-Level Pneumonia Detection", "source": "arXiv", "url": "https://arxiv.org/abs/1711.05225"}
       ]
     }
     ```
   - Server formats this into professional Google Docs API requests with fonts, styles, headings, and links
   - Writes to the doc in one batch

5. Done. The doc looks like a real report.

---

### Example: three agents on one topic

**User submits:**
```
Task: "Research the impact of AI on healthcare"
Doc ID: 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
Research mode: on
```

Three agents are idle.

**Step 1 — Manager splits the task** using `TASK_SPLIT_PROMPT`:
```json
[
  "Find how AI is used in medical diagnosis today. Find at least 2 real examples with sources.",
  "Find how AI is used in drug discovery. Find at least 2 real examples with sources.",
  "Find risks and concerns about AI in healthcare. Find at least 3 real concerns with sources."
]
```

**Step 2 — Server pre-writes the doc outline** (before agents start browsing):

The doc looks like this in Google Docs (with real fonts and styles applied):

```
╔══════════════════════════════════════════════════╗
║  AI in Healthcare — Research Report              ║  ← Title (Georgia 24pt bold)
║  Generated: Feb 22, 2026                         ║  ← Subtitle (grey 10pt)
╠══════════════════════════════════════════════════╣
║                                                  ║
║  1. Medical Diagnosis                            ║  ← Heading 2 (bold 14pt)
║  ⏳ In progress — agent-abc123                   ║  ← Grey italic placeholder
║                                                  ║
║  2. Drug Discovery                               ║  ← Heading 2
║  ⏳ Queued                                       ║  ← Grey italic placeholder
║                                                  ║
║  3. Risks and Concerns                           ║  ← Heading 2
║  ⏳ Queued                                       ║  ← Grey italic placeholder
║                                                  ║
║  Summary                                         ║  ← Heading 2
║  ⏳ Pending — written when all sections complete  ║
║                                                  ║
║  Bibliography                                    ║  ← Heading 2
║  ⏳ Pending                                      ║
║                                                  ║
╚══════════════════════════════════════════════════╝
```

Each placeholder line contains the agent ID (if assigned) or "Queued" (if not yet claimed). This is the **subtask claiming** — anyone looking at the doc can see which agent is working on which section.

**Step 3 — Three tasks are queued**, each tagged with its section number and the same doc_id. Manager assigns one to each idle agent.

**Step 4 — Agents browse in parallel.** No coordination needed. Each one browses for its own subtopic. They never write to the doc. As each agent starts, the server updates the placeholder to show `⏳ In progress — agent-xxx`.

**Step 5 — Each agent finishes.** When each agent's AI returns `null`, the server:
- Calls AI with `RESEARCH_SUMMARIZE_PROMPT` and the browsing history
- Gets structured JSON back (findings + sources + bibliography entries)
- Formats with styles (see formatting section below)
- Replaces the `⏳ In progress...` placeholder for that section with the real content
- Updates the placeholder to `✓ Complete — agent-abc123`

**Step 6 — All three sections are filled.** Server then:
- Reads the full doc
- Calls AI with all three sections: *"Write a 2-sentence summary of these findings."*
- Writes the summary section
- Compiles all bibliography entries from all agents into the Bibliography section, sorted alphabetically
- Replaces the last two `⏳ Pending` placeholders with the final content

**Result in the doc:**

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  AI in Healthcare — Research Report                          ║  ← Georgia 24pt bold
║  Generated: Feb 22, 2026                                     ║  ← Grey 10pt
║                                                              ║
║  1. Medical Diagnosis                                        ║  ← Bold 14pt
║                                                              ║
║  AI systems have reached clinical-grade accuracy in           ║  ← Normal 11pt
║  diagnosing diseases from medical images. DeepMind's          ║
║  retinal scan model detected over 50 eye conditions           ║
║  with 94% accuracy in clinical trials (De Fauw et al.,        ║
║  2018). Stanford's CheXNet matched radiologist-level          ║
║  performance in pneumonia detection from chest X-rays         ║
║  (Rajpurkar et al., 2017).                                   ║
║                                                              ║
║  Sources:                                                    ║  ← Bold 10pt
║  • DeepMind Blog — deepmind.com/blog/ai-eye-disease          ║  ← 10pt, blue link
║  • Stanford ML Group — stanfordmlgroup.github.io/...          ║  ← 10pt, blue link
║                                                              ║
║  ✓ Complete — agent-abc123                                   ║  ← Green italic 9pt
║                                                              ║
║  2. Drug Discovery                                           ║
║  ...                                                         ║
║                                                              ║
║  3. Risks and Concerns                                       ║
║  ...                                                         ║
║                                                              ║
║  Summary                                                     ║  ← Bold 14pt
║                                                              ║
║  AI in healthcare shows strong results in diagnosis and       ║  ← Normal 11pt
║  drug discovery, but raises serious concerns around data      ║
║  privacy, algorithmic bias, and clinical liability.           ║
║  Regulatory frameworks are still catching up to the pace      ║
║  of adoption.                                                ║
║                                                              ║
║  Bibliography                                                ║  ← Bold 14pt
║                                                              ║
║  De Fauw, J. et al. (2018). Clinically applicable deep       ║  ← Normal 10pt
║    learning for diagnosis. Nature Medicine.                   ║
║    https://nature.com/articles/s41591-018-0107-6              ║  ← Blue link
║                                                              ║
║  Rajpurkar, P. et al. (2017). CheXNet: Radiologist-Level     ║
║    Pneumonia Detection. arXiv.                                ║
║    https://arxiv.org/abs/1711.05225                           ║  ← Blue link
║                                                              ║
║  ...more entries from other agents...                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## How the doc formatting works

The server builds Google Docs API requests. The AI never touches any of this — the server applies fixed styles:

### Style map

| Element | Font | Size | Style | Color |
|---------|------|------|-------|-------|
| Document title | Georgia | 24pt | bold | black |
| Date subtitle | Arial | 10pt | normal | grey `#888888` |
| Section heading | Arial | 14pt | bold | black |
| Body text | Arial | 11pt | normal | black |
| Inline citation | Arial | 11pt | normal | black (part of body) |
| "Sources:" label | Arial | 10pt | bold | black |
| Source link | Arial | 10pt | normal | blue `#1155CC`, underlined, hyperlinked |
| Status line (in progress) | Arial | 9pt | italic | grey `#999999` |
| Status line (complete) | Arial | 9pt | italic | green `#38761D` |
| Bibliography entry | Arial | 10pt | normal | black |
| Bibliography URL | Arial | 10pt | normal | blue `#1155CC`, hyperlinked |

### How the server builds the API requests

For each section, the server creates a batch of requests like this:

```python
requests = []

# Insert the body text
requests.append({
    "insertText": {
        "location": {"index": insert_at},
        "text": body_text + "\n"
    }
})

# Style the body text
requests.append({
    "updateTextStyle": {
        "range": {"startIndex": insert_at, "endIndex": insert_at + len(body_text)},
        "textStyle": {
            "fontFamily": "Arial",
            "fontSize": {"magnitude": 11, "unit": "PT"}
        },
        "fields": "fontFamily,fontSize"
    }
})

# Insert each source as a bullet with a hyperlink
for source in sources:
    link_text = f"{source['name']} — {source['url']}\n"
    requests.append({
        "insertText": {
            "location": {"index": source_insert_at},
            "text": link_text
        }
    })
    # Make it a clickable link
    requests.append({
        "updateTextStyle": {
            "range": {"startIndex": source_insert_at, "endIndex": source_insert_at + len(link_text)},
            "textStyle": {
                "link": {"url": source["url"]},
                "foregroundColor": {"color": {"rgbColor": {"red": 0.07, "green": 0.33, "blue": 0.8}}},
                "fontSize": {"magnitude": 10, "unit": "PT"}
            },
            "fields": "link,foregroundColor,fontSize"
        }
    })
    # Make it a bullet point
    requests.append({
        "createParagraphBullets": {
            "range": {"startIndex": source_insert_at, "endIndex": source_insert_at + len(link_text)},
            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
        }
    })
```

This is all server code. The AI returns structured data and the server applies the formatting template. The AI never needs to know about Google Docs API.

---

## Subtask claiming in the doc

The doc itself shows who is working on what. This is visible to anyone who opens the Google Doc — even if they don't have access to the dashboard.

### Status lifecycle for each section

```
⏳ Queued                          ← task created, no agent yet
⏳ In progress — agent-abc123      ← agent started browsing
⏳ Writing — agent-abc123           ← agent finished browsing, server is writing
✓ Complete — agent-abc123           ← section written
```

### How claiming works

When the manager assigns a sub-task to an agent, it also updates the placeholder in the doc:

```python
# In manager.py, after assigning a sub-task
if task_row.get("section_label") and task_row.get("doc_id"):
    docs.update_placeholder(
        task_row["doc_id"],
        task_row["section_label"],
        f"⏳ In progress — {agent.id}"
    )
```

When the agent finishes and the server writes the real content, the placeholder is replaced with the findings, and a small green status line is appended:

```python
# In agent.py, at the end of _extract_and_write()
self.docs.write_section(self.doc_id, self.section_label, formatted_content)
self.docs.update_placeholder(
    self.doc_id,
    self.section_label,
    f"✓ Complete — {self.id}"
)
```

### What the doc looks like during research (live)

If someone opens the Google Doc while agents are still working:

```
AI in Healthcare — Research Report
Generated: Feb 22, 2026

1. Medical Diagnosis
AI systems have reached clinical-grade accuracy in diagnosing
diseases from medical images...
Sources:
• DeepMind Blog — https://deepmind.com/blog/...
• Stanford ML Group — https://stanfordmlgroup.github.io/...
✓ Complete — agent-abc123

2. Drug Discovery
⏳ In progress — agent-def456

3. Risks and Concerns
⏳ Queued

Summary
⏳ Pending — written when all sections complete

Bibliography
⏳ Pending
```

You can see at a glance: section 1 is done, section 2 is being researched, section 3 hasn't started yet.

---

## The summarize prompt (what the AI returns)

After browsing, the server calls the AI with `RESEARCH_SUMMARIZE_PROMPT`. The prompt asks for structured JSON so the server can format it properly:

```
RESEARCH_SUMMARIZE_PROMPT = """
You just browsed the web to research a topic. Based on what you saw
on screen during your browsing session, write a structured summary.

Your subtopic was: {subtopic}

Return a JSON object with this exact structure:
{
  "body": "Your findings as 1-2 clear paragraphs. Cite sources inline
           using (Author, Year) format. Only include facts you actually
           saw on screen — do not guess or use prior knowledge.",
  "sources": [
    {
      "name": "Name of the website or article",
      "url": "The URL you visited (from the browser address bar)"
    }
  ],
  "bibliography": [
    {
      "author": "Author or Organization name",
      "year": "2024",
      "title": "Title of the article or page",
      "source": "Website name",
      "url": "https://full-url-here"
    }
  ]
}

Rules:
- Only include sources you actually visited and saw on screen.
- If you could not find good information, set body to
  "No relevant information was found for this subtopic." and
  leave sources and bibliography empty.
- Keep the body concise: 4-8 sentences maximum.
- Use (Author, Year) inline citations that match bibliography entries.
"""
```

The server parses the JSON, applies the style template, and writes to the doc. If parsing fails, it writes the raw text as a fallback.

---

## What changes in each file

### `server/prompts.py`

**Remove** `RESEARCH_PROMPT` (47 lines).

**Add:**
- `RESEARCH_BROWSE_PROMPT` — simple browse-only prompt, no doc actions, just desktop control
- `RESEARCH_SUMMARIZE_PROMPT` — structured JSON extraction prompt (shown above)

Keep `TASK_PROMPT` and `TASK_SPLIT_PROMPT` unchanged.

---

### `server/agent.py`

**Remove:**
- `_handle_doc_command()`, `_read_doc()`, `_write_doc()`, `_prefetch_doc()`
- The `read_doc`/`write_doc` branch in `act()`
- The `doc_read` state flag

**Add:**
- `section_label` field — set by manager when assigning a sub-task (e.g. `"1. Medical Diagnosis"`)
- `_extract_and_write()` — called once after browsing finishes:
  1. Sends history + `RESEARCH_SUMMARIZE_PROMPT` to AI
  2. Parses JSON response
  3. Calls `self.docs.write_formatted_section()` with the structured data
  4. Updates the doc placeholder to `✓ Complete`

**Change:**
- `assign()` — uses `RESEARCH_BROWSE_PROMPT` for research mode
- `done()` — if research_mode, calls `_extract_and_write()` before returning

---

### `server/google_docs.py`

**Add:**

`create_outline(doc_id, title, sections)`:
- Writes the title heading (Georgia 24pt bold)
- Writes the date subtitle (grey 10pt)
- Writes each section heading (Arial 14pt bold) with a `⏳ Queued` placeholder under it
- Writes Summary and Bibliography headings with `⏳ Pending` placeholders

`write_formatted_section(doc_id, section_label, findings_json)`:
- Finds the section heading in the doc using anchor search
- Replaces the placeholder text with:
  - Body paragraphs (Arial 11pt)
  - "Sources:" label (Arial 10pt bold)
  - Bulleted source links (Arial 10pt, blue, hyperlinked)
  - `✓ Complete — agent-id` status line (green 9pt italic)

`write_bibliography(doc_id, entries)`:
- Finds the "Bibliography" heading
- Writes all bibliography entries sorted alphabetically by author
- Each entry formatted as: `Author (Year). Title. Source. URL`
- URLs are blue and hyperlinked

`write_summary(doc_id, summary_text)`:
- Finds the "Summary" heading
- Writes the summary paragraph (Arial 11pt)

`update_placeholder(doc_id, section_label, status_text)`:
- Finds the section heading, looks for the existing `⏳` line
- Replaces it with the new status text (styled appropriately: grey for in-progress, green for complete)

Keep all existing `read()` and `write()` methods.

---

### `server/manager.py`

**Add** task splitting in `dispatch_tasks()`:

When a research task comes in and 2+ agents are idle:
1. Call AI with `TASK_SPLIT_PROMPT` → list of subtopics
2. Call `docs.create_outline(doc_id, title, subtopics)` to pre-structure the doc
3. Create one sub-task per subtopic, tagged with `section_label` and `doc_id`
4. Delete the original parent task
5. Normal dispatch loop assigns sub-tasks to idle agents

When a sub-task is assigned to an agent:
- Call `docs.update_placeholder(doc_id, section_label, "⏳ In progress — {agent_id}")`

**Add** summary trigger: after all sub-tasks for a doc are complete:
- Read the full doc
- Call AI: "Write a 2-sentence summary of these findings"
- Call `docs.write_summary(doc_id, summary)`
- Compile bibliography entries from all agents → `docs.write_bibliography(doc_id, all_entries)`

---

### `server/database.py`

**Add:**
- `get_task_by_id(task_id)` — fetch a single task row
- `delete_task(task_id)` — remove the parent task after splitting
- `section_label` column on tasks table — stores the section heading text for sub-tasks
- `parent_task_id` column on tasks table — links sub-tasks to the original task so the manager knows when all sub-tasks for a doc are done

---

## What gets removed

| Removed | Where | Lines |
|---------|-------|-------|
| `RESEARCH_PROMPT` | `prompts.py` | ~47 |
| `_handle_doc_command()` | `agent.py` | ~15 |
| `_read_doc()` | `agent.py` | ~10 |
| `_write_doc()` | `agent.py` | ~30 |
| `_prefetch_doc()` | `agent.py` | ~5 |
| `read_doc`/`write_doc` branch in `act()` | `agent.py` | ~3 |
| `doc_read` state field | `agent.py` | ~3 |
| **Total** | | **~113 lines** |

---

## Edge cases and how they're handled

**Only 1 agent available when research task arrives:**
No splitting. Agent browses the full topic. Server calls summarize once. Writes one section (no outline, just heading + body + sources + bibliography). Clean result.

**Agent browses but finds nothing useful:**
The summarize prompt tells the AI to return `"No relevant information was found."` with empty sources. The server writes that text to the section. Nothing crashes. The section is not blank — it explicitly says nothing was found.

**Doc pre-structure write fails** (no internet, bad credentials):
Agents are still dispatched. When they finish, `write_formatted_section()` appends to the end of the doc. Research is not lost — just not in the outline structure.

**One agent finishes early, others still working:**
Each agent writes independently. Order does not matter. The anchor system finds the right section heading regardless of when the agent finishes.

**Task splits into more subtopics than idle agents:**
Cap at the number of idle agents. If there are 3 agents and 5 subtopics, create 3 sub-tasks. The other 2 subtopics are dropped. Keep it simple.

**`TASK_SPLIT_PROMPT` returns bad JSON:**
Fall back to no splitting. Assign the original task to one agent. Log the error.

**Summarize prompt returns bad JSON:**
Fall back: write the raw text response to the doc as a plain paragraph (Arial 11pt, no special formatting). Still better than nothing.

**`RESEARCH_SUMMARIZE_PROMPT` returns sources that weren't actually visited:**
The prompt says "only include sources you actually visited." Hallucinated sources are an AI reliability issue, not a code issue. The formatting will be correct regardless.

**Two agents try to write to the same doc at the same time:**
Google Docs API handles concurrent writes. Each write targets a different anchor (different section heading), so they don't conflict.

---

## Implementation order

1. **`prompts.py`** — add `RESEARCH_BROWSE_PROMPT` and `RESEARCH_SUMMARIZE_PROMPT`, remove `RESEARCH_PROMPT`
2. **`agent.py`** — remove doc methods, add `section_label` field and `_extract_and_write()`
3. **`google_docs.py`** — add `create_outline()`, `write_formatted_section()`, `write_bibliography()`, `write_summary()`, `update_placeholder()`
4. **`database.py`** — add `section_label` and `parent_task_id` columns, add `get_task_by_id()` and `delete_task()`
5. **`manager.py`** — add task splitting, doc outline creation, placeholder updates, and summary trigger
6. Test with 1 agent (no splitting), then 2+ agents (with splitting)
