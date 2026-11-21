# Pharmeazor LLM-only baseline

Run date: 20 November 2026

## Model and test path

The configured model is `openai/gpt-oss-120b` through the Groq-compatible API. I ran the 50 questions from the supplied v2 bank through the same `generate_answer` function used by `POST /ask`. Each request contained only its question; no reference passage, expected answer, or scoring rubric was sent to the model. The app does not set temperature, `top_p`, `seed`, or `max_tokens`, so the provider defaults were used.

All 50 questions received a successful answer. One first attempt for N3-05 hit a Groq rate limit and succeeded when retried. The raw JSONL file preserves all 51 attempts, including that error and the retry. The median latency across successful answers was 7.23 seconds. None of the 50 answers included a source URL or a source-file citation.

## Main findings

The model is not reliable enough for unsupervised clinical answers. It often answered fluently while changing drug identity, mixing products or doses, adding unsupported detail, or failing to abstain when the answer was outside the corpus.

- **N1-01 (fixed smoke question):** got the usual 3 g/day maximum and mentioned four-hour spacing, but gave conflicting 4 g/day weight guidance (70 kg, then “close” to 60 kg) instead of the benchmark's ≥50 kg threshold. It also omitted the warning not to take two 1,000 mg tablets at once, added unsupported alcohol/drug-risk details, and gave no source citation. Applying the supplied four-point rubric to this question alone: 2/4 (criterion 1 and minimum interval met; weight condition inconsistent; RCP-grounding point not evidenced).
- **N1-09:** identified DETENSIEL as mirabegron and gave a 25–50 mg regimen; the bank identifies DETENSIEL as bisoprolol.
- **N2-07:** substituted unrelated amoxicillin regimens for the two cited formulations, missing the key difference between monotherapy and the amoxicillin/clavulanate combination.
- **N3-05:** said bisoprolol might be considered with monitoring in severe asthma, while the reference answer says DETENSIEL is contraindicated for that case.
- **TR-03:** described EXFORGE as perindopril/indapamide instead of amlodipine/valsartan, missing the corpus anomaly the question was designed to expose.
- **TR-05:** correctly warned against a 1,000 mg tablet for a 20 kg child, then gave incorrect conversions for a 250 mg/5 mL liquid in its example.
- **HS-03, HS-06, HS-07:** invented an Algerian price/reimbursement estimate, answered with out-of-corpus furosemide doses, and supplied a dose for a one-month-old despite the benchmark requiring abstention.

There were some good responses, including the 8 kg infant dose calculation in N3-03 and appropriate refusals to prescribe in HS-01 and invent an expiry date in HS-05. These do not offset the wrong drug identities, unsupported clinical detail, and failures on the deliberate trap and abstention questions.

## RAG comparison status

I could not run Test B: the project has a corpus loader/chunker, but no embedding model, vector index, retriever, or RAG answer route. `data/loader.py` can create RAG chunks; it does not retrieve passages for a question.

The benchmark cites 78 passages. All 78 source URLs resolve in the raw processed corpus, and 77 excerpts match after whitespace normalization. However, 21 cited file paths are absent from the filtered `data/outputs_data` corpus that `DrugCorpusLoader` reads by default. The v2 bank includes original-corpus records that the filtered loader cannot retrieve, so the corpus version must be aligned before comparing LLM-only with RAG.

## Benchmark and integration issues

- The workbook has 50 questions and complete expected answers, rubrics, typical errors, and source passages. Its LLM-only and RAG response/score/date fields were blank before this run.
- The overall score scale is 0–4, but 10 question rubrics each list five separate one-point criteria. I did not calculate a misleading aggregate score; make those scales consistent before comparing averages.
- The project setting and direct `/ask` calls use `openai/gpt-oss-120b` via Groq. The older `report.md` claim about local BioMistral is not backed by code: `medsafe_api` contains a CSV but no model service.
- The frontend PharmaTutor calls `/api/v1/conversation/chat`, while `ai_api/main.py` exposes `/ask` and `/health`. The Django interaction proxy calls `/api/v1/interactions/analyze`, which is also absent from this FastAPI app. So the configured model works through the direct `/ask` code path, but the existing tutor and interaction flows are not wired to it.
- Project descriptions also differ: the root README describes a medication-information project, the architecture report calls it an interaction checker, and the supplied benchmark is for corpus-grounded clinical Q&A/RAG. Choose one mission before treating this as a product evaluation.

## Files

- `raw_responses.jsonl` — raw answers and attempt metadata for all 50 questions, plus the initial failed request and its retry.
- The supplied question bank and workbook remain unchanged.
