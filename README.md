# Flight Voucher Generator

Paste raw flight-booking text → Gemini extracts structured fields → a
PDF voucher (matching your reference ticket's design) is generated for
download. Built for variable numbers of flight legs and passengers, so it
works for direct or connecting flights and any party size.

## A. Architecture

- **Frontend:** Plain HTML/CSS/JS (`app/static/index.html`), served directly
  by the backend. No build step, no framework — one page, one job.
- **Backend:** FastAPI (`app/main.py`).
- **Extraction:** Gemini API (`app/gemini_extractor.py`), model
  `gemini-2.5-flash` by default, forced JSON output.
- **PDF generation:** ReportLab Platypus (`app/pdf_builder.py`). The template
  is **rebuilt in code**, not overlaid on the original PDF — the sample
  ticket has variable-length tables (1–2 flight legs, N passengers), and a
  fixed x/y overlay can't handle that. The rebuilt template reproduces the
  reference design's colors, section headers, callouts, and table styling,
  with the logo omitted as requested.

### File structure
```
ticket-pdf-app/
├── app/
│   ├── main.py              # FastAPI app + /api/generate route
│   ├── gemini_extractor.py  # Gemini prompt, call, JSON validation/defaults
│   ├── pdf_builder.py       # ReportLab voucher template
│   └── static/
│       └── index.html       # UI
├── requirements.txt
├── Procfile                  # Render start command
├── render.yaml                # Optional one-click Render blueprint
├── .env.example
└── README.md
```

### API endpoints
- `GET /` — serves the UI.
- `GET /api/health` — health check.
- `POST /api/generate` — body `{"text": "<raw ticket text>"}`, returns the
  generated PDF as a binary stream (`Content-Disposition: attachment`).
  Optional header `X-Access-Key` if `ACCESS_KEY` is set (see below).

### Error handling
- Empty input → `400`.
- Gemini call fails or returns invalid JSON → `502` with the raw error
  surfaced (helps you debug prompt/model issues quickly).
- PDF build fails (e.g. unexpected data shape) → `500`.
- All extracted fields are normalized/defaulted server-side
  (`gemini_extractor._normalize`) so a partial/odd Gemini response never
  crashes PDF generation — missing scalars become `"None"`, missing lists
  become `[]`.

## B. Extraction schema

```json
{
  "booking_reference": "string",
  "operating_carrier": "string",
  "journey_type": "string",
  "booking_status": "string",
  "flights": [
    {
      "flight_number": "string", "type": "string", "duration": "string",
      "departure_time": "string", "departure_date": "string",
      "departure_airport_code": "string", "departure_airport_name": "string",
      "departure_city_country": "string",
      "arrival_time": "string", "arrival_date": "string",
      "arrival_airport_code": "string", "arrival_airport_name": "string",
      "arrival_city_country": "string",
      "layover_after": null
    }
  ],
  "passengers": [{ "name": "string", "seat_assignment": "string" }],
  "baggage": [
    {
      "passenger_name": "string",
      "cabin_baggage_allowance": ["string"],
      "checked_hold_bag": "string"
    }
  ]
}
```
Missing scalar → `"None"`. Missing list → `[]`.

## C. Gemini prompt

See `EXTRACTION_PROMPT` in `app/gemini_extractor.py` — it embeds the schema
above, the "None" / empty-list rule, and the `layover_after` rule (only the
leg immediately before a connection gets a layover; the final/only leg is
`null`). Edit that one constant if you need to add fields later.

## D. Running locally

```bash
cd ticket-pdf-app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then fill in GEMINI_API_KEY
export $(cat .env | xargs)   # or use a tool like `direnv`/`python-dotenv`
uvicorn app.main:app --reload
```
Open http://localhost:8000.

## E. Deploying on Render (free tier)

1. Push this folder to a GitHub repo.
2. On Render: **New → Web Service** → connect the repo.
   - If you commit `render.yaml`, Render will read it automatically
     (Blueprint) and you can skip the manual field entry below.
   - Otherwise set manually:
     - **Environment:** Python 3
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
     - **Plan:** Free
3. Add environment variables (Render dashboard → Environment):
   - `GEMINI_API_KEY` = your key (required)
   - `GEMINI_MODEL` = `gemini-2.5-flash` (optional, this is the default)
   - `ACCESS_KEY` = any secret string (optional — see below)
4. Deploy. Render gives you a `https://<service>.onrender.com` URL.

**Free tier note:** the service spins down after ~15 minutes idle and takes
30–50s to wake up on the next request — expect that delay on the first
request after inactivity. Not a bug, just the free tier.

### Optional protection
Since this will be a public URL, anyone who finds it can trigger Gemini
calls on your API key. If you want a minimal gate without full auth, set
`ACCESS_KEY` in Render's env vars. Then any client must send header
`X-Access-Key: <that value>` or requests get `401`. Leave it unset if you're
fine leaving it open — the app works either way with zero code changes.

## F. Testing

**Extraction accuracy:** paste a few varied ticket texts (direct flight,
connecting flight, missing fields, 1 passenger, 5 passengers) into the UI
and check the returned JSON is sane before trusting the PDF. To debug
extraction alone without generating a PDF, you can temporarily call
`app/gemini_extractor.py`'s `extract_ticket_fields()` directly in a Python
shell and print the dict.

**PDF generation:** run the app locally, generate a PDF, and open it. Check:
- Direct flight (no `layover_after`) → no connection-transfer callout.
- Connecting flight → callout appears between legs correctly.
- 1 passenger vs many → passenger/baggage tables resize correctly, no
  overlap.
- Long airport names / notices → text wraps instead of overflowing (uses
  `Paragraph`, not fixed-width `drawString`, so this should hold).

**Deployment:** after deploying, hit `GET /api/health` first to confirm the
service is up, then run one full generate from the UI. If `/api/generate`
returns `502`, check the Render logs — it almost always means
`GEMINI_API_KEY` is missing/invalid or the model name is wrong.
