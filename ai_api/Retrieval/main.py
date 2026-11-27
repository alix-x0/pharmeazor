from pathlib import Path
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Pharmeazor AI API"
    GROQ_API_KEY: Optional[str] = None
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "pharmaceutical_drugs"


settings = Settings()
app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Pharmaceutical Assistant: BGE-M3 Hybrid RAG & Knowledge Graph Engine",
    version="2.0.0",
)
logger = logging.getLogger(__name__)

QUESTION_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Pharmeazor AI</title>
  <style>
    :root{color-scheme:light;font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;color:#19352e;background:#f3f6f4}
    *{box-sizing:border-box}body{margin:0;padding:7vh 18px}.shell{max-width:760px;margin:auto}
    .card{background:white;border:1px solid #dce6e1;border-radius:18px;padding:clamp(22px,5vw,40px);box-shadow:0 12px 35px #153b2b0c}
    h1{margin:0 0 8px;font-size:clamp(28px,5vw,40px);letter-spacing:-.03em}.intro{color:#5c7068;margin:0 0 28px}
    label{display:block;font-weight:650;margin-bottom:8px}textarea{display:block;width:100%;min-height:125px;resize:vertical;padding:14px;border:1px solid #b9c9c2;border-radius:10px;font:inherit;color:inherit}
    textarea:focus{outline:3px solid #176b5525;border-color:#176b55}.actions{display:flex;align-items:center;gap:14px;margin-top:14px}
    button{border:0;border-radius:9px;padding:11px 20px;background:#176b55;color:white;font:inherit;font-weight:650;cursor:pointer}
    button:disabled{opacity:.55;cursor:wait}.hint{font-size:13px;color:#657a72}.status{margin:18px 0 0;color:#9a3d2e}
    .answer{margin-top:24px;border-top:1px solid #e2eae6;padding-top:22px}.answer[hidden]{display:none}
    .answer h2{font-size:18px;margin:0 0 5px}.asked,.model{font-size:13px;color:#657a72;margin:0 0 12px}
    .answer-text{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;color:#243e35}
  </style>
</head>
<body><main class="shell"><section class="card">
  <h1>Pharmeazor AI</h1>
  <p class="intro">Ask a question and see the model's response. Supports standard LLM queries and hybrid pharmaceutical RAG search.</p>
  <form id="ask-form">
    <label for="question">Your question</label>
    <textarea id="question" name="question" required maxlength="4000" placeholder="Type your question here"></textarea>
    <div class="actions"><button id="submit" type="submit">Ask</button><span class="hint">Powered by Groq &amp; BGE-M3 RAG</span></div>
  </form>
  <p id="status" class="status" role="status" aria-live="polite"></p>
  <section id="answer-card" class="answer" aria-live="polite" hidden>
    <h2>Answer</h2><p id="asked" class="asked"></p><p id="model" class="model"></p>
    <p id="answer-text" class="answer-text"></p>
  </section>
</section></main>
<script>
  const form=document.getElementById('ask-form');
  const questionField=document.getElementById('question');
  const submitButton=document.getElementById('submit');
  const status=document.getElementById('status');
  const answerCard=document.getElementById('answer-card');
  form.addEventListener('submit',async(event)=>{
    event.preventDefault();
    const question=questionField.value.trim();
    if(!question)return;
    submitButton.disabled=true;
    status.textContent='Thinking…';
    answerCard.hidden=true;
    try{
      const response=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});
      const payload=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(payload.detail||`Request failed (${response.status})`);
      document.getElementById('asked').textContent=`Question: ${payload.question}`;
      document.getElementById('model').textContent=`Model: ${payload.model}`;
      document.getElementById('answer-text').textContent=payload.answer;
      answerCard.hidden=false;
      status.textContent='';
    }catch(error){status.textContent=error.message||'Could not get a response.';}
    finally{submitButton.disabled=false;}
  });
</script></body></html>"""


# =====================================================================
# Request / Response Models
# =====================================================================

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

    @field_validator("question", mode="before")
    @classmethod
    def strip_question(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000, description="Clinical query or medication search")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to retrieve")
    dense_weight: float = Field(default=1.0, ge=0.0, le=2.0)
    sparse_weight: float = Field(default=0.3, ge=0.0, le=2.0)
    dci_filter: Optional[str] = Field(default=None, description="Filter by active ingredient (DCI)")
    section_category: Optional[str] = Field(default=None, description="Filter by clinical section")


# =====================================================================
# Core Endpoints
# =====================================================================

@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return HTMLResponse(QUESTION_PAGE)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "groq_model": settings.GROQ_MODEL,
        "groq_key_configured": bool(settings.GROQ_API_KEY),
        "architecture": {
            "rag_available": True,
            "knowledge_graph_ontology_available": True,
        },
    }


def generate_answer(question: str) -> dict[str, str]:
    question = question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")
    if not settings.GROQ_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured. Set it in ai_api/.env.",
        )

    try:
        with OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.GROQ_BASE_URL,
            timeout=30.0,
        ) as client:
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful general-purpose assistant. Answer clearly and concisely "
                            "in the user's language. You do not have access to Pharmeazor's collected medicine data "
                            "or external sources; never claim that you searched or cited them. For medical "
                            "questions, give general educational information, not diagnosis or personalized treatment."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
            )
    except OpenAIError as exc:
        logger.warning("Groq chat completion failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="The Groq request failed. Check the API key, model, and provider availability.",
        ) from exc

    answer = response.choices[0].message.content if response.choices else None
    if not answer:
        raise HTTPException(status_code=502, detail="Groq returned an empty answer.")

    return {"question": question, "answer": answer, "model": settings.GROQ_MODEL}


@app.post("/ask")
def ask(body: AskRequest) -> dict[str, str]:
    return generate_answer(body.question)


@app.get("/ask", response_class=HTMLResponse)
def ask_page() -> HTMLResponse:
    return HTMLResponse(QUESTION_PAGE)


# =====================================================================
# RAG Endpoints
# =====================================================================

@app.post("/rag/search")
def rag_search(request: RAGSearchRequest) -> Dict[str, Any]:
    """
    Performs hybrid semantic and lexical search across pharmaceutical chunks
    using BGE-M3 and Qdrant.
    """
    try:
        from ai_api.rag.retriever import search_drugs
        results = search_drugs(
            query=request.query,
            top_k=request.top_k,
            dense_weight=request.dense_weight,
            sparse_weight=request.sparse_weight,
            dci_filter=request.dci_filter,
            section_category=request.section_category,
        )
        return {
            "query": request.query,
            "total_retrieved": len(results),
            "results": [r.to_dict() for r in results],
        }
    except Exception as exc:
        logger.error(f"RAG search failed: {exc}")
        raise HTTPException(status_code=500, detail=f"RAG search error: {str(exc)}")


# =====================================================================
# Knowledge Graph Endpoints
# =====================================================================

@app.get("/kg/ontology")
def get_ontology() -> Dict[str, Any]:
    """
    Returns the defined pharmaceutical ontology entity types and relation types.
    """
    try:
        from ai_api.Augmentation.knowledge_graph.ontology import EntityType, RelationType
        return {
            "entity_types": [e.value for e in EntityType],
            "relation_types": [r.value for r in RelationType],
        }
    except Exception as exc:
        logger.error(f"Failed to load ontology: {exc}")
        raise HTTPException(status_code=500, detail=f"Ontology error: {str(exc)}")
