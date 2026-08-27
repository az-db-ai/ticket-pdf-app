# Safrna Ticket-to-PDF Generator — Project Summary

A web app that takes raw, unstructured flight-booking text, extracts
structured fields using the Gemini API, and generates a polished,
branded PDF e-ticket receipt for download. Built for Safrna Travel and
Tourism.

---

## 1. What the app does

1. User pastes raw ticket/booking text (an email, a copy-pasted
   confirmation, a messy booking-system export — whatever they have)
   into a text box in the browser.
2. The backend sends that text to the Gemini API with a strict
   extraction prompt and gets back structured JSON (booking reference,
   flight segments, passengers, baggage rules, etc.).
3. The backend feeds that JSON into a PDF builder that renders a
   branded "Safrna" e-ticket receipt, matching an agency-provided design
   spec (rounded cards, soft shadows, navy/blue palette, a status pill,
   a dark info bar, etc.).
4. The PDF streams back to the browser as a download.

Handles variable data shapes: 1 or more flight segments (direct or
multi-leg/connecting), any number of passengers, and any baggage rules
found in the source text — nothing is hardcoded to a fixed number of
rows.

---

## 2. Architecture

- **Backend:** FastAPI (Python) — `app/main.py`
- **Extraction:** Gemini API (`google-generativeai` SDK) — `app/gemini_extractor.py`
- **PDF generation:** ReportLab (Platypus + custom Flowables for rounded
  cards, pill badges, and icons) — `app/pdf_builder.py`
- **Frontend:** Plain HTML/CSS/JS, single page, no framework — `app/static/index.html`
- **Fonts:** Lato (embedded TTFs, Regular/Bold/Italic/Black) — `app/fonts/`

### File structure
```
ticket-pdf-app/
├── app/
│   ├── main.py              # FastAPI app + /api/generate route
│   ├── gemini_extractor.py  # Gemini prompt, call, JSON validation/defaults
│   ├── pdf_builder.py       # ReportLab PDF template (all visual design lives here)
│   ├── fonts/                # Lato-Regular/Bold/Italic/Black.ttf
│   └── static/
│       └── index.html        # UI (paste box, Generate button, download link)
├── requirements.txt
├── Procfile                   # for Render deployment (not currently used)
├── render.yaml                 # optional Render blueprint (not currently used)
├── .env.example
├── .gitignore
└── README.md
```

### API endpoints
- `GET /` — serves the UI
- `GET /api/health` — health check
- `POST /api/generate` — body `{"text": "<raw ticket text>"}` → returns
  the generated PDF as a binary download. Optional `X-Access-Key` header
  check if `ACCESS_KEY` env var is set (off by default).

---

## 3. Data schema (what Gemini extracts)

```json
{
  "booking_reference": "string",
  "booking_status": "string",
  "operating_carrier": "string",
  "segments": [
    {
      "segment_label": "string",       // e.g. "Outbound Segment (Part 1)", "Return Segment"
      "flight_number": "string",
      "class": "string",
      "aircraft": "string",
      "operated_by": "string",         // codeshare operator, or "None"
      "duration": "string",
      "meal": "string",
      "departure_time": "string",       // ALWAYS 24-hour "HH:MM"
      "departure_date": "string",
      "departure_airport_name": "string",
      "departure_airport_code": "string",
      "departure_terminal": "string",
      "arrival_time": "string",         // ALWAYS 24-hour "HH:MM"
      "arrival_date": "string",
      "arrival_day_offset": "string",   // "+1 Day" etc, or "" if none
      "arrival_airport_name": "string",
      "arrival_airport_code": "string",
      "arrival_terminal": "string"
    }
  ],
  "seat_route_labels": ["string"],      // e.g. ["JED-CGK", "SIN-JED"]
  "passengers": [
    {
      "name": "string",
      "airline_code": "string",
      "electronic_ticket_no": "string",
      "rewards_program": "string",
      "seat_assignments": ["string"]    // one entry per seat_route_labels, same order
    }
  ],
  "checked_baggage": "string",
  "carry_on_rules": ["string"]
}
```

Rules baked into the extraction prompt (`app/gemini_extractor.py`):
- Missing scalar field → `"None"`. Missing list → `[]`.
- All times forced to 24-hour format regardless of source format.
- Seat assignments must be padded/aligned to match `seat_route_labels`
  length exactly (never shorter, never dropped).
- `layover`/route grouping is taken exactly as shown in the source, not
  inferred or merged by the model.

`_normalize()` in `gemini_extractor.py` re-validates and defensively
fills in any missing keys server-side, so a slightly malformed Gemini
response never crashes PDF generation.

---

## 4. Visual design

The final PDF design follows an agency-provided style spec:

- **Palette:** light blue-gray page background (`#F4F6F9`), white rounded
  cards with soft drop shadows, navy (`#1A365D`) primary text, accent
  blue (`#2B6CB0`) for airport codes/links, muted gray (`#718096`) for
  labels, green pill badge for "CONFIRMED" status.
- **Header:** "SAFRNA" logo wordmark + "TRAVEL AND TOURISM" tagline +
  small plane-icon badge, "E-TICKET RECEIPT" label and a status pill on
  the right.
- **Info bar:** full-width dark navy rounded card with Booking Ref /
  Airline / Class / Passenger count.
- **Flight itinerary cards:** one per segment, each with departure and
  arrival airport code (big, blue) tightly clustered with the airport
  name/terminal underneath, a deliberately larger gap, then the big time
  display, then the date directly under it (tight). A dashed connector
  with a small plane icon sits between departure and arrival.
- **Passenger table:** clean rows (no colored header band), passenger
  name / e-ticket number / rewards program / seat assignments.
- **Baggage panels:** rounded cards in a row, each with a suitcase icon,
  a label, a bold "NN KG" headline number, and a short description.
  Generated dynamically from however many baggage rules are found (not
  fixed to exactly 3).
- **Footer:** appears on every page — a short "Important Travel
  Information" notice, a centered "Thank you for choosing Safrna" line,
  and "Page X of Y" pagination.
- **Fonts:** Lato (Regular/Bold/Black/Italic), embedded as TTFs. Chosen
  as a substitute for Inter — Inter is only distributed as a variable
  font, which ReportLab can't split into separate static Bold/Black
  weights, so Lato was used to satisfy the same "clean geometric sans
  with real bold weights" brief.
- No logo image is used anywhere (per instruction) — the "logo" is
  styled text plus a small vector plane icon drawn directly in code.

---

## 5. Bugs found and fixed along the way

These are worth knowing about if you (or anyone) touches `pdf_builder.py`
again:

1. **Seat assignments truncated to one seat on multi-leg tickets.**
   Fixed by explicitly telling Gemini in the prompt that
   `seat_assignments` must have one entry per `seat_route_labels` entry,
   padded with `"None"` if a leg's seat is missing — never shortened.

2. **Full-page background wiped out all content.** The page-background
   fill was originally drawn in the footer function, which runs *after*
   all page content in the PDF's draw order — so it silently painted
   over the entire page, leaving only the footer text visible (page text
   was still there if you extracted it, just invisible). Fixed by moving
   the background fill into a `PageTemplate.onPage` callback, which
   ReportLab runs *before* content is drawn for that page.

3. **"Page X of Y" showed the wrong total (off-by-one), and created a
   phantom extra page.** The two-pass page-counting canvas had an extra
   iteration outside its main loop. Fixed by following the standard
   ReportLab "NumberedCanvas" recipe exactly (count = number of saved
   page states, draw footer + `showPage()` once per saved state, nothing
   extra after the loop).

4. **Capitalized section headers had no visible space between words**
   (e.g. "OUTBOUND SEGMENT" rendered as "OUTBOUNDSEGMENT"). Root cause:
   the letter-spacing trick joined every character (including real
   spaces) with an inserted space, but ReportLab collapses any run of
   regular space characters down to a single space no matter how many
   there are — so word gaps and letter gaps ended up the same width.
   Fixed by using non-breaking spaces (`\u00A0`) for letter-tracking,
   which are not collapsed, and using three of them at real word
   boundaries so they're clearly wider than the single nbsp between
   letters. Verified by measuring actual character x-positions in the
   output PDF (word-boundary gaps ended up ~9–10pt vs ~5–6pt between
   letters).

5. **Baggage weights showed both kg and lbs (or lbs only).** Added
   `_kg_only()` in `pdf_builder.py`, which: drops redundant `"(X lbs)"`
   parentheticals next to a kg value, drops the lb part of combined
   `"Xlb/Ykg"` formats, and converts any standalone lb-only mention to
   kg. Applied to both the bold headline number and the description text
   in every baggage panel.

6. **One-page ticket vs. multi-page.** Early versions of the styled
   template overflowed onto extra, mostly-empty pages for tickets with
   several segments. Fixed iteratively by measuring actual flowable
   heights (`flowable.wrap()`) against available frame height and
   trimming margins, card padding, and inter-element spacing rather than
   guessing. A 3-segment round-trip with 2 passengers still spans 2
   pages, which is reasonable given how much content that genuinely is —
   this is not a bug, just a lot of data.

---

## 6. Design adaptations (where the ticket data didn't match the spec exactly)

- The style spec's top info bar assumed "Booking Ref / Airline / Ticket #
  / Class" — but ticket numbers are per-*passenger*, not one global
  value, so that slot was swapped for **passenger count** instead
  (ticket numbers are still shown correctly, per passenger, in the
  Passenger Details table).
- The style spec assumed exactly 3 baggage panels. Real tickets have
  anywhere from 1 to several baggage rules (checked baggage + N
  carry-on rules), so panels are generated dynamically and wrap to a new
  row of 3 if there are more than 3.
- The reference "flat design" ticket (the very first sample) had
  variable-length tables (1–2 flight legs, N passengers), so rather than
  overlaying text onto a static background PDF at fixed coordinates
  (which only works for one exact row-count), the whole template is
  rebuilt in code with dynamic tables — this is what makes it correctly
  handle a 1-passenger direct flight and a 4-passenger connecting flight
  with the same code path.

---

## 7. Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Your Gemini API key |
| `GEMINI_MODEL` | No (defaults to `gemini-2.5-flash`) | Which Gemini model to call |
| `ACCESS_KEY` | No | If set, `/api/generate` requires header `X-Access-Key` matching this value. Leave unset for no protection. |

`.env` is git-ignored and must never be committed — it holds the real
API key.

---

## 8. Running locally (quick reference)

```powershell
cd ticket-pdf-app
venv\Scripts\Activate.ps1
Get-Content .env | ForEach-Object { if ($_ -match '^\s*([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim()) } }
uvicorn app.main:app --reload
```
Then open http://localhost:8000.

---

## 9. Status as of this document

Working end-to-end locally: paste text → Gemini extraction → styled PDF
→ download. Tested against multiple real ticket samples including
single-leg, multi-leg/connecting, single-passenger, and multi-passenger
bookings. Deployment to Render was scoped and prepared (`Procfile`,
`render.yaml`, instructions in `README.md`) but is not currently in use
— the project is being kept local / pushed to GitHub for now, not
deployed.
