from __future__ import annotations

import json
import os
from threading import Lock

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from extraction.env import load_dotenv
from extraction.paths import ROOT
from extraction.runner import image_path, iter_run, list_receipts, load_summaries, save_upload

load_dotenv()
app = FastAPI(title="ExtractBench", docs_url=None, redoc_url=None)
run_lock = Lock()


class RunRequest(BaseModel):
    pipelines: list[str] = Field(default_factory=list)
    ids: list[str] = Field(default_factory=list)


@app.get("/api/health")
def health() -> dict:
    receipts = list_receipts()
    return {"ok": True, "labeled": sum(r["scored"] for r in receipts),
            "with_image": sum(r["has_image"] for r in receipts),
            "vlm_ready": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))}


@app.get("/api/receipts")
def receipts() -> dict:
    return {"receipts": list_receipts()}


@app.get("/api/receipts/{receipt_id}/image")
def receipt_image(receipt_id: str) -> FileResponse:
    try:
        return FileResponse(image_path(receipt_id))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/leaderboard")
def leaderboard() -> dict:
    return {"summaries": load_summaries()}


@app.post("/api/uploads")
async def upload(file: UploadFile = File(...)) -> dict:
    try:
        return save_upload(file.filename or "upload.jpg", await file.read())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/run")
def run(body: RunRequest) -> StreamingResponse:
    if not run_lock.acquire(blocking=False):
        raise HTTPException(409, "A scan is already running.")

    def stream():
        try:
            for event in iter_run(body.pipelines, body.ids):
                yield f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"
        except (ValueError, FileNotFoundError) as exc:
            yield f"event: run_error\ndata: {json.dumps({'detail': str(exc)})}\n\n"
        finally:
            run_lock.release()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


app.mount("/", StaticFiles(directory=str(ROOT / "web"), html=True), name="ui")
