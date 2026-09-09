from __future__ import annotations

import json
import os
from threading import Lock

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from extraction.env import load_dotenv
from extraction.paths import ROOT
from extraction.runner import (
    image_path,
    iter_run,
    list_dataset_payloads,
    list_documents,
    load_summaries,
    save_label,
    save_upload,
)

load_dotenv()
app = FastAPI(title="ExtractBench", docs_url=None, redoc_url=None)
run_lock = Lock()


class RunRequest(BaseModel):
    pipelines: list[str] = Field(default_factory=list)
    ids: list[str] = Field(default_factory=list)
    dataset: str = "sroie"


class LabelRequest(BaseModel):
    dataset: str = "personal"
    id: str
    fields: dict[str, str | None]
    notes: str | None = None


@app.get("/api/health")
def health() -> dict:
    datasets = list_dataset_payloads()
    sroie = next((row for row in datasets if row["id"] == "sroie"), {})
    return {
        "ok": True,
        "labeled": sroie.get("labeled", 0),
        "with_image": sroie.get("with_image", 0),
        "vlm_ready": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "datasets": datasets,
    }


@app.get("/api/datasets")
def datasets() -> dict:
    return {"datasets": list_dataset_payloads()}


@app.get("/api/receipts")
def receipts(dataset: str = Query("sroie")) -> dict:
    try:
        return {"dataset": dataset, "receipts": list_documents(dataset)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/receipts/{receipt_id}/image")
def receipt_image(receipt_id: str, dataset: str = Query("sroie")) -> FileResponse:
    try:
        return FileResponse(image_path(receipt_id, dataset))
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/leaderboard")
def leaderboard(dataset: str = Query("sroie")) -> dict:
    try:
        return {"dataset": dataset, "summaries": load_summaries(dataset)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/uploads")
async def upload(file: UploadFile = File(...), dataset: str = Query("personal")) -> dict:
    try:
        return save_upload(file.filename or "upload.jpg", await file.read(), dataset)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/labels")
def labels(body: LabelRequest) -> dict:
    try:
        return save_label(body.dataset, body.id, body.fields, body.notes)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/run")
def run(body: RunRequest) -> StreamingResponse:
    if not run_lock.acquire(blocking=False):
        raise HTTPException(409, "A scan is already running.")

    def stream():
        try:
            for event in iter_run(body.pipelines, body.ids, body.dataset):
                yield f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"
        except (ValueError, FileNotFoundError) as exc:
            yield f"event: run_error\ndata: {json.dumps({'detail': str(exc)})}\n\n"
        finally:
            run_lock.release()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


app.mount("/", StaticFiles(directory=str(ROOT / "web"), html=True), name="ui")
