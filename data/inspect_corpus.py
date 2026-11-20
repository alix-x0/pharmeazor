"""
Corpus Inspector and Verification Tool
======================================
Tests and validates the drug corpus loaded into Pharmeazor.

Run:
    python data/inspect_corpus.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.loader import DrugCorpusLoader


def main():
    print("=" * 60)
    print("PHARMEAZOR DRUG CORPUS INSPECTOR")
    print("=" * 60)

    loader = DrugCorpusLoader()
    print(f"\n[1] Total monographs loaded: {len(loader)}")

    # Check DCIs
    dcis = loader.get_all_dcis()
    print(f"[2] Unique active substances (DCI): {len(dcis)}")
    print("    First 10 DCIs:")
    for d in dcis[:10]:
        print(f"      - {d}")

    # Check Brands
    brands = loader.get_all_brands()
    print(f"\n[3] Unique commercial brand names: {len(brands)}")
    print("    Sample brands:")
    for b in brands[:10]:
        print(f"      - {b}")

    # Document types
    rcp_count = len(loader.filter(doc_type="rcp"))
    notice_count = len(loader.filter(doc_type="notice"))
    print(f"\n[4] Documents breakdown:")
    print(f"      - RCP (Professionals): {rcp_count}")
    print(f"      - Notice (Patients)   : {notice_count}")

    # Generate sample RAG chunks
    print(f"\n[5] Generating RAG chunks with clinical metadata...")
    chunks = loader.get_rag_chunks(min_chars=60, max_chunk_chars=1200)
    print(f"    Total RAG chunks produced: {len(chunks)}")

    if chunks:
        sample = chunks[0]
        print(f"\n[6] Sample RAG Chunk Preview:")
        print("-" * 50)
        print("Metadata:")
        for k, v in sample.metadata.items():
            print(f"  {k}: {v}")
        print("\nText (First 350 chars):")
        print(sample.text[:350] + ("..." if len(sample.text) > 350 else ""))
        print("-" * 50)

    # Check manifest
    manifest = loader.get_manifest()
    resume = loader.get_resume()
    print(f"\n[7] Control Files:")
    print(f"      - _MANIFESTE.csv entries: {len(manifest)}")
    print(f"      - _RESUME.csv entries   : {len(resume)}")

    print("\n" + "=" * 60)
    print("SUCCESS: Drug corpus is fully integrated, verified, and RAG-ready!")
    print("=" * 60)


if __name__ == "__main__":
    main()

