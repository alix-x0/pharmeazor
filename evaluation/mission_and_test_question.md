# Mission and canonical test question

## Mission

Pharmeazor helps people in Algeria find and understand medicine-use and safety information in product documents for the project's 40 target ingredients. It identifies the product and source, preserves differences between documents, and abstains when the available corpus does not support an answer. It does not diagnose or prescribe, and it does not claim live price or stock information.

The evaluation asks whether retrieval from the corpus improves answer quality over the same LLM answering without retrieved passages.

## Canonical test: N1-01

**Question**

> Chez un adulte de 60 kg, quelle est la dose journalière maximale de DOLIPRANE 1000 mg en règle générale, et dans quelle condition peut-on aller jusqu'à 4 g par jour ?

**Expected answer — evaluator only**

The usual maximum is 3,000 mg per day. A dose up to 4,000 mg per day is allowed only on medical advice, without risk factors, for a patient weighing at least 50 kg. Doses must be separated by at least four hours, and the patient must not take two 1,000 mg tablets at once.

**Scoring criteria — one point each**

These four points follow the supplied v2 benchmark. The expected answer also says not to take two 1,000 mg tablets at once; record that omission as a safety error, but do not count it as a fifth benchmark point.

1. States 3,000 mg/day as the usual maximum.
2. States that 4,000 mg/day is only on medical advice and for a patient weighing at least 50 kg. The expected answer also requires no risk factors.
3. States a minimum four-hour interval between doses.
4. Grounds the answer in the RCP rather than relying only on model memory. For the LLM-only run, award this point only if the answer includes a checkable source citation; otherwise record it as not evidenced.

## Test protocol

- **LLM-only run:** send only the question. Do not send the expected answer, rubric, source passage, or any other bank fields.
- **RAG run:** send the same question and only passages actually returned by the retriever. Record the retrieved passages and retrieval settings.
- Record the model identifier, date, parameters, latency, raw answer, per-criterion score, and observed errors for each run.
- Keep the two runs on the same model and settings. Do not treat an oracle passage inserted by hand as a normal RAG result.

The 50-question v2 bank remains the full benchmark. N1-01 is the fixed smoke question for quickly checking the standalone model path.
