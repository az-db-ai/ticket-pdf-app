import os
from io import BytesIO

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.gemini_extractor import extract_ticket_fields
from app.pdf_builder import build_ticket_pdf

app = FastAPI(title="Ticket to PDF Generator")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Optional lightweight protection. If ACCESS_KEY is unset, no check is enforced.
ACCESS_KEY = os.environ.get("ACCESS_KEY")


class TicketRequest(BaseModel):
    text: str


def _check_access(x_access_key: str | None):
    if ACCESS_KEY and x_access_key != ACCESS_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing access key")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/generate")
def generate_pdf(payload: TicketRequest, x_access_key: str | None = Header(default=None)):
    _check_access(x_access_key)

    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Ticket text is required")

    try:
        fields = extract_ticket_fields(payload.text)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Extraction failed: {exc}") from exc

    try:
        pdf_bytes = build_ticket_pdf(fields)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc

    filename = f"ticket_{fields.get('booking_reference', 'voucher')}.pdf".replace(" ", "_")
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
