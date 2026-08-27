"""
Gemini-based extraction of structured flight-ticket fields from raw text.
"""
import json
import os
import re

import google.generativeai as genai

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------------------------
# Prompt sent to Gemini. Keep this in sync with pdf_builder.py's expectations.
# ---------------------------------------------------------------------------
EXTRACTION_PROMPT = """You are a data-extraction engine for a travel agency. You will be given
raw, unstructured text describing a flight booking (an email, a copy-pasted
confirmation, a voucher, etc.). The trip may be one-way, round-trip, or
multi-segment (outbound part 1, outbound part 2, return, etc.). Extract the
fields below and return ONLY a single valid JSON object — no markdown
fences, no commentary, no explanation.

RULES:
- If a scalar (single-value) field is missing or not mentioned in the text, set it to the string "None".
- If a list (segments, passengers, carry_on_rules) has no items found, return an empty list [].
- Do not invent data. Only extract what is explicitly present.
- Dates: keep the same wording as the source text if possible; otherwise use "Sat, 20 Jun 2026" style.
- Times: ALWAYS output in 24-hour "HH:MM" format (e.g. "14:30", not "2:30 PM"). If the source uses 12-hour AM/PM, convert it yourself. Every departure_time and arrival_time must be 24-hour, no exceptions.
- "arrival_day_offset": if the arrival lands on a later calendar day than departure (often shown as "+1 Day" or similar), set this to "+1 Day" (or "+2 Day" etc. if shown). Otherwise set it to "" (empty string), not "None".
- "segment_label": use the label given in the source text for that flight leg, e.g. "Outbound Segment (Part 1)", "Outbound Segment (Part 2)", "Return Segment", "Flight 1". If the source has no explicit label, infer a reasonable one (e.g. "Flight 1", "Flight 2").
- "operated_by": only set this if the source explicitly says the segment is operated by a different airline than the main operating_carrier (codeshare). Otherwise "None".
- Passenger names: keep exactly as written (e.g. "SMITH / JOHN MR").
- "seat_route_labels": a top-level list of the route labels used for seat assignments exactly as shown in the source (e.g. ["JED-CGK", "SIN-JED"]). These may NOT map 1:1 to the number of segments — extract them exactly as grouped in the source's seat column header, do not merge or split them yourself.
- Each passenger's "seat_assignments" MUST be a list the SAME LENGTH as "seat_route_labels", in the same order, one seat code per route label. If a seat for a specific route is missing, use "None" in that position — never drop it or shorten the list.
- "checked_baggage": a single plain-language sentence describing the checked baggage policy (pieces, weight, dimensions) if given, applying to all passengers unless the source says otherwise.
- "carry_on_rules": a list of short strings, one per distinct carry-on rule/sector mentioned (e.g. "SV Sectors: 1 piece up to 12 KG (26 lbs)"). Empty list if none mentioned.
- Ignore any citation artifacts like "[cite: 4]" in the source text — they are not part of the ticket data.

Return JSON matching EXACTLY this schema:

{
  "booking_reference": string,
  "booking_status": string,
  "operating_carrier": string,
  "segments": [
    {
      "segment_label": string,
      "flight_number": string,
      "class": string,
      "aircraft": string,
      "operated_by": string,
      "duration": string,
      "meal": string,
      "departure_time": string,
      "departure_date": string,
      "departure_airport_name": string,
      "departure_airport_code": string,
      "departure_terminal": string,
      "arrival_time": string,
      "arrival_date": string,
      "arrival_day_offset": string,
      "arrival_airport_name": string,
      "arrival_airport_code": string,
      "arrival_terminal": string
    }
  ],
  "seat_route_labels": [string],
  "passengers": [
    {
      "name": string,
      "airline_code": string,
      "electronic_ticket_no": string,
      "rewards_program": string,
      "seat_assignments": [string]
    }
  ],
  "checked_baggage": string,
  "carry_on_rules": [string]
}

RAW TICKET TEXT:
---
{raw_text}
---

Return only the JSON object.
"""

_DEFAULT_RESULT = {
    "booking_reference": "None",
    "booking_status": "None",
    "operating_carrier": "None",
    "segments": [],
    "seat_route_labels": [],
    "passengers": [],
    "checked_baggage": "None",
    "carry_on_rules": [],
}


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_ticket_fields(raw_text: str) -> dict:
    """Call Gemini and return a validated dict matching the schema above."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    prompt = EXTRACTION_PROMPT.replace("{raw_text}", raw_text)

    response = model.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )

    raw_output = _strip_code_fences(response.text or "")

    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned invalid JSON: {exc}\nRaw output: {raw_output}") from exc

    return _normalize(data)


def _normalize(data: dict) -> dict:
    """Fill in any missing keys with safe defaults so pdf_builder never KeyErrors."""
    result = dict(_DEFAULT_RESULT)
    result.update({k: v for k, v in data.items() if k in _DEFAULT_RESULT})

    for key in ("booking_reference", "booking_status", "operating_carrier", "checked_baggage"):
        if not result.get(key):
            result[key] = "None"

    seat_route_labels = result.get("seat_route_labels") or []
    if isinstance(seat_route_labels, str):
        seat_route_labels = [seat_route_labels]
    result["seat_route_labels"] = [str(x) for x in seat_route_labels]
    n_routes = len(result["seat_route_labels"])

    normalized_segments = []
    for s in result.get("segments") or []:
        normalized_segments.append({
            "segment_label": s.get("segment_label") or "None",
            "flight_number": s.get("flight_number") or "None",
            "class": s.get("class") or "None",
            "aircraft": s.get("aircraft") or "None",
            "operated_by": s.get("operated_by") or "None",
            "duration": s.get("duration") or "None",
            "meal": s.get("meal") or "None",
            "departure_time": s.get("departure_time") or "None",
            "departure_date": s.get("departure_date") or "None",
            "departure_airport_name": s.get("departure_airport_name") or "None",
            "departure_airport_code": s.get("departure_airport_code") or "None",
            "departure_terminal": s.get("departure_terminal") or "None",
            "arrival_time": s.get("arrival_time") or "None",
            "arrival_date": s.get("arrival_date") or "None",
            "arrival_day_offset": s.get("arrival_day_offset") or "",
            "arrival_airport_name": s.get("arrival_airport_name") or "None",
            "arrival_airport_code": s.get("arrival_airport_code") or "None",
            "arrival_terminal": s.get("arrival_terminal") or "None",
        })
    result["segments"] = normalized_segments

    normalized_passengers = []
    for p in result.get("passengers") or []:
        seats = p.get("seat_assignments") or []
        if isinstance(seats, str):
            seats = [seats]
        seats = [str(x) if x else "None" for x in seats]
        if n_routes:
            if len(seats) < n_routes:
                seats = seats + ["None"] * (n_routes - len(seats))
            elif len(seats) > n_routes:
                seats = seats[:n_routes]
        normalized_passengers.append({
            "name": p.get("name") or "None",
            "airline_code": p.get("airline_code") or "None",
            "electronic_ticket_no": p.get("electronic_ticket_no") or "None",
            "rewards_program": p.get("rewards_program") or "None",
            "seat_assignments": seats,
        })
    result["passengers"] = normalized_passengers

    carry_on = result.get("carry_on_rules") or []
    if isinstance(carry_on, str):
        carry_on = [carry_on]
    result["carry_on_rules"] = [str(x) for x in carry_on]

    return result