"""
BioMistral Medical Explanation and Conversation Service

Uses the BioMistral-Instruct-MIMIC-7B-DARE GGUF model for GPU inference via llama-cpp-python.
The model is downloaded once from HuggingFace and cached locally.
"""

import logging
from pathlib import Path
from functools import lru_cache
from typing import List, Optional

from huggingface_hub import hf_hub_download
from llama_cpp import Llama

logger = logging.getLogger(__name__)

HF_REPO   = "mradermacher/BioMistral-Instruct-MIMIC-7B-DARE-GGUF"
GGUF_FILE = "BioMistral-Instruct-MIMIC-7B-DARE.Q4_K_M.gguf"

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# Number of transformer layers offloaded to GPU.
# 35 covers the full 7B model on a 6 GB+ GPU; lower this if you hit OOM errors.
N_GPU_LAYERS = 35

EXPLAIN_SYSTEM_PROMPT_PATIENT = (
    "You are a clinical pharmacology assistant providing safety advice to patients. "
    "Provide a clean, accessible experience designed for non-technical users and elderly populations. "
    "Your role is to provide a brief, single-paragraph safety advisory for a drug-drug interaction. "
    "Do NOT mention specific drug names in your response. "
    "Detail the specific side effects of the interaction in simple terms, "
    "and explicitly mention which patient populations are most at risk (e.g., children, pregnant women, elderly). "
    "Keep responses concise (under 150 words). "
    "DO NOT use markdown formatting, bullet points, or newlines."
)

EXPLAIN_SYSTEM_PROMPT_PHARMACIST = (
    "You are a clinical pharmacology assistant providing professional advice to pharmacists. "
    "Provide a denser, clinical-grade view that supports their dispensing decisions and reduces errors at the counter. "
    "Your role is to provide a brief, single-paragraph safety advisory for a drug-drug interaction. "
    "Do NOT mention specific drug names in your response. "
    "You must detail the specific side effects, the precise pharmacological mechanism, "
    "and explicitly mention which patient populations are most at risk (e.g., children, pregnant women, "
    "elderly, renal or hepatic impairment). "
    "Keep responses concise (under 150 words). "
    "DO NOT use markdown formatting, bullet points, or newlines."
)

CONVERSATION_SYSTEM_PROMPT_PHARMACIST = (
    "You are PharmaTutor, an expert clinical pharmacology assistant designed to help "
    "pharmacists and pharmaceutical vendors strengthen their clinical knowledge. "
    "Provide a denser, clinical-grade view that supports their dispensing decisions and reduces errors at the counter. "
    "You can explain drug mechanisms, pharmacokinetics, pharmacodynamics, therapeutic uses, "
    "contraindications, adverse effects, counselling points, and drug-drug interactions "
    "at a professional level suitable for licensed pharmacists. "
    "You may also quiz the user, present clinical scenarios, or walk through case studies "
    "to support active learning and training. "
    "Always be precise, evidence-based, and cite pharmacological reasoning. "
    "If asked about a specific patient situation, remind the user that your answers are "
    "educational and do not replace clinical judgement or prescriber authority. "
    "You must ALWAYS reply EXCLUSIVELY in French. DO NOT include English translations. "
    "Keep answers very short, concise, and precise. Limit your responses to 3 lines maximum."
)

CONVERSATION_SYSTEM_PROMPT_PATIENT = (
    "You are Medora, a helpful medical assistant for patients. "
    "Provide a clean, accessible experience designed for non-technical users and elderly populations. "
    "Explain medical concepts in simple, reassuring terms. "
    "Always advise the user to consult their doctor or pharmacist for medical decisions. "
    "You must ALWAYS reply EXCLUSIVELY in French. DO NOT include English translations. "
    "Keep answers very short, concise, and easy to understand. Limit your responses to 3 lines maximum."
)

LEVEL_CONTEXT = {
    "DANGER": (
        "This is a MAJOR interaction. Describe why this combination is dangerous "
        "and what serious adverse effects can occur. "
        "Emphasize that medical supervision is essential and the combination should "
        "generally be avoided unless closely monitored."
    ),
    "CAUTION": (
        "This is a MODERATE interaction. Describe the risk and which patients are "
        "most vulnerable. Advise monitoring and when to seek medical advice."
    ),
    "COMPATIBLE": (
        "This combination appears safe under normal conditions. "
        "Give a brief reassurance and note any minor precautions if relevant."
    ),
}


def _model_path() -> Path:
    """Return the local path for the GGUF file, downloading it if needed."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODELS_DIR / GGUF_FILE

    if dest.exists():
        logger.info("Model already cached at %s", dest)
        return dest

    logger.info("Downloading %s from HuggingFace (one-time, ~4.5 GB).", GGUF_FILE)
    downloaded = hf_hub_download(
        repo_id=HF_REPO,
        filename=GGUF_FILE,
        local_dir=str(MODELS_DIR),
        local_dir_use_symlinks=False,
    )
    logger.info("Model saved to %s", downloaded)
    return Path(downloaded)


@lru_cache(maxsize=1)
def _load_model() -> Llama:
    """Load the Llama model once and cache it for the lifetime of the process."""
    path = _model_path()
    logger.info("Loading BioMistral into memory (n_gpu_layers=%d).", N_GPU_LAYERS)
    model = Llama(
        model_path=str(path),
        n_gpu_layers=N_GPU_LAYERS,
        n_ctx=4096,
        n_batch=512,
        verbose=False,
    )
    logger.info("BioMistral model loaded successfully.")
    return model


def load() -> None:
    """Pre-load the model at application startup to avoid a slow first request."""
    _load_model()


def _build_explain_prompt(drug_a: str, drug_b: str, level: str, original_level: str, role: str = "pharmacist") -> str:
    """Build a [INST]-style prompt for a single-shot interaction explanation."""
    from app.services.ddinter_service import ddinter_service

    system_prompt = EXPLAIN_SYSTEM_PROMPT_PHARMACIST if role == "pharmacist" else EXPLAIN_SYSTEM_PROMPT_PATIENT
    logger.info("Building explain prompt for role: %s. System prompt starts with: %s", role, system_prompt[:50])

    meta_a = ddinter_service.get_drug_metadata(drug_a)
    meta_b = ddinter_service.get_drug_metadata(drug_b)

    def format_meta(meta):
        if not meta:
            return ""
        parts = [p for p in (meta.get("product_type"), meta.get("route")) if p and p.lower() != "unknown"]
        return f" ({', '.join(parts)})" if parts else ""

    type_a = format_meta(meta_a)
    type_b = format_meta(meta_b)

    level_ctx = LEVEL_CONTEXT.get(level, LEVEL_CONTEXT["CAUTION"])
    user_msg = (
        f"A patient is taking two medications: {drug_a}{type_a} (refer to this as Drug A) "
        f"and {drug_b}{type_b} (refer to this as Drug B). "
        f"The interaction between them is classified as '{original_level}' severity ({level}). "
        f"{level_ctx} "
        f"Provide a concise generic advisory (using 'Drug A' and 'Drug B' instead of their real names) for this specific interaction. "
        f"Remember to include specific side effects, mechanisms, and target vulnerable populations in a single paragraph without markdown."
    )
    return f"[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{user_msg} [/INST]"


def _build_conversation_prompt(
    history: List[dict],
    system_prompt: Optional[str] = None,
    role: str = "pharmacist",
) -> str:
    """
    Build a multi-turn [INST] prompt from a conversation history.
    history is a list of {"role": "user"|"assistant", "content": "..."} dicts.
    """
    if system_prompt is None:
        system_prompt = CONVERSATION_SYSTEM_PROMPT_PHARMACIST if role == "pharmacist" else CONVERSATION_SYSTEM_PROMPT_PATIENT
    prompt = "<s>"
    first_user = True

    for msg in history:
        role = msg["role"]
        content = msg["content"].strip()

        if role == "user":
            if first_user:
                prompt += f"[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{content} [/INST]"
                first_user = False
            else:
                prompt += f"[INST] {content} [/INST]"
        elif role == "assistant":
            prompt += f" {content} </s>"

    return prompt


def generate_explanation(
    drug_a: str,
    drug_b: str,
    level: str,
    original_level: str,
    role: str = "pharmacist",
    max_tokens: int = 250,
    temperature: float = 0.3,
) -> str:
    """
    Generate a generic medical explanation for a drug-drug interaction pair.

    Args:
        drug_a:         Name of the first drug (used for metadata lookup).
        drug_b:         Name of the second drug.
        level:          Severity bucket - DANGER | CAUTION | COMPATIBLE.
        original_level: DDInter label - Major | Moderate | Minor.
        max_tokens:     Cap on generated tokens.
        temperature:    Lower = more deterministic.

    Returns:
        Plain-text medical advisory string.
    """
    model = _load_model()
    prompt = _build_explain_prompt(drug_a, drug_b, level, original_level, role=role)

    logger.debug("Generating explanation for %s + %s [%s]", drug_a, drug_b, level)
    output = model(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=0.9,
        repeat_penalty=1.1,
        stop=["</s>", "[INST]"],
    )
    return output["choices"][0]["text"].strip()


def generate_conversation_reply(
    history: List[dict],
    role: str = "pharmacist",
    max_tokens: int = 512,
    temperature: float = 0.4,
) -> str:
    """
    Generate the next assistant reply for a multi-turn conversation.

    Args:
        history:     Full conversation history as role/content dicts.
                     The last item must be a user message.
        max_tokens:  Maximum tokens to generate.
        temperature: Sampling temperature.

    Returns:
        Plain-text assistant reply.

    Raises:
        ValueError: If the last history entry is not a user message.
    """
    if not history or history[-1]["role"] != "user":
        raise ValueError("The last message in history must be a user message.")

    model = _load_model()
    prompt = _build_conversation_prompt(history, role=role)

    logger.debug("Generating conversation reply (turns=%d)", len(history))
    output = model(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=0.92,
        repeat_penalty=1.1,
        stop=["</s>", "[INST]"],
    )
    return output["choices"][0]["text"].strip()
