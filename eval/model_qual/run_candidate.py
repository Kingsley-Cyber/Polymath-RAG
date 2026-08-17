"""Model-qualification sidecar: runs any GLiNER model on a port."""
import os, sys, tomllib
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel, Field

MODEL_ID = os.environ["GLINER_MODEL_ID"]
MODEL_REV = os.environ["GLINER_MODEL_REV"]
PORT = int(os.environ.get("GLINER_PORT", "8746"))

class InferRequest(BaseModel):
    task: str = "entity"
    text: str
    threshold: float = 0.5
    labels: list[str] = Field(default_factory=list)

class Span(BaseModel):
    text: str; start: int; end: int; label: str; score: float

class InferResponse(BaseModel):
    task: str; spans: list[Span]; model_release: str

@asynccontextmanager
async def lifespan(app):
    from gliner import GLiNER
    model = GLiNER.from_pretrained(MODEL_ID, revision=MODEL_REV,
                                   cache_dir=str(Path.home()/".cache"/"polymath"/"gliner"))
    app.state.model = model.to("mps")
    yield

app = FastAPI(title=f"Candidate {MODEL_ID}", lifespan=lifespan)

@app.get("/health")
async def health(): return {"status": "ok", "model": MODEL_ID}

@app.get("/ready")
async def ready():
    try:
        app.state.model.predict_entities("probe", ["test"], threshold=0.9)
        return {"ready": True}
    except: return {"ready": False}

@app.post("/infer", response_model=InferResponse)
async def infer(req: InferRequest):
    spans = app.state.model.predict_entities(req.text, req.labels, threshold=req.threshold)
    return InferResponse(task=req.task, spans=[
        Span(text=s["text"], start=s["start"], end=s["end"],
             label=s["label"].split(":")[0].strip(), score=s["score"]) for s in spans],
        model_release=f"{MODEL_ID}@{MODEL_REV[:8]}")
