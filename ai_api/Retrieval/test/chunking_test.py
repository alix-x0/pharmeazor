"""
Test Suite for Pharmeazor RAG Chunking Engine
=============================================
Tests chunking strategies, section-awareness, contextual headers,
recursive semantic splitting, and real dataset integration using
the curated 40-DCI pharmaceutical corpus in data/outputs_data.

Run:
    python -m ai_api.Retrieval.test.chunking_test
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Retrieval.chunking import (
    DEFAULT_DATA_DIR,
    DEFAULT_PROCESSED_DIR,
    ChunkingConfig,
    DrugChunk,
    DrugChunker,
    RecursiveSemanticSplitter,
    build_context_header,
    categorize_section,
    chunk_corpus,
    chunk_document,
    chunk_file,
    clean_text,
    default_chunker,
    generate_chunk_id,
    get_all_dossiers,
    normalize_section_key,
)

DATA_OUTPUTS_DIR = DEFAULT_DATA_DIR


class TestChunkingUnit(unittest.TestCase):
    """Unit tests for individual components of the chunking engine."""

    def test_default_initialization(self):
        """Test default configuration parameters."""
        config = ChunkingConfig()
        self.assertEqual(config.min_chunk_chars, 50)
        self.assertEqual(config.max_chunk_chars, 1400)
        self.assertEqual(config.overlap_chars, 180)
        self.assertTrue(config.add_context_header)
        self.assertEqual(config.header_style, "full")

        chunker = DrugChunker()
        self.assertIsNotNone(chunker.splitter)
        self.assertEqual(chunker.splitter.max_chars, 1400)

    def test_clean_text(self):
        """Test whitespace and scraping artifact cleanup."""
        raw = "Line 1\r\n\r\n\r\n\r\nLine 2\nRedirection vers le haut de page\nParacétamol ................. 1000 mg   "
        cleaned = clean_text(raw)
        self.assertNotIn("Redirection vers le haut de page", cleaned)
        self.assertNotIn("\r", cleaned)
        self.assertNotIn("\n\n\n", cleaned)
        self.assertIn("Paracétamol ... 1000 mg", cleaned)
        self.assertTrue(cleaned.endswith("1000 mg"))

    def test_normalize_section_key(self):
        """Test key normalization for strings, lists, and None."""
        self.assertEqual(normalize_section_key("Posologie et Mode"), "posologie_et_mode")
        self.assertEqual(normalize_section_key("4.2"), "4_2")
        self.assertEqual(normalize_section_key(None), "")
        # DailyMed list-type key
        self.assertEqual(
            normalize_section_key(["indications", "Indications and Usage"]),
            "indications_indications_and_usage",
        )

    def test_categorize_section(self):
        """Test mapping of section keys and numbers to canonical categories."""
        self.assertEqual(categorize_section("posologie", "4.2"), "posology")
        self.assertEqual(categorize_section("dosage_and_administration"), "posology")
        self.assertEqual(categorize_section("contre_indications", "4.3"), "contraindications")
        self.assertEqual(categorize_section("mises_en_garde", "4.4"), "warnings")
        self.assertEqual(categorize_section("interactions", "4.5"), "interactions")
        self.assertEqual(categorize_section("effets_indesirables", "4.8"), "adverse_effects")
        self.assertEqual(categorize_section("surdosage", "4.9"), "overdose")
        self.assertEqual(categorize_section("fertilite_grossesse", "4.6"), "pregnancy_lactation")
        self.assertEqual(categorize_section("indications", "4.1"), "indications")
        self.assertEqual(categorize_section("composition", "2"), "composition")

    def test_build_context_header(self):
        """Test context header construction in full and compact modes."""
        header_full = build_context_header(
            brand="DOLIPRANE",
            dci="PARACÉTAMOL",
            dosage_form="1000 mg, comprimé",
            lab="PROPHARMAL SPA",
            source="anpp",
            priority=1,
            doc_type="rcp",
            section_title="Posologie et mode d'administration",
            section_number="4.2",
            part_idx=1,
            total_parts=2,
            style="full",
        )
        self.assertIn("MÉDICAMENT: DOLIPRANE", header_full)
        self.assertIn("DCI: PARACÉTAMOL", header_full)
        self.assertIn("FORME/DOSAGE: 1000 mg, comprimé", header_full)
        self.assertIn("SOURCE: ANPP (P1)", header_full)
        self.assertIn("SECTION: 4.2 Posologie et mode d'administration [Partie 1/2]", header_full)

        header_compact = build_context_header(
            brand="DOLIPRANE",
            dci="PARACÉTAMOL",
            dosage_form="1000 mg",
            lab="PROPHARMAL",
            source="anpp",
            priority=1,
            doc_type="rcp",
            section_title="Contre-indications",
            style="compact",
        )
        self.assertIn("DOLIPRANE", header_compact)
        self.assertIn("[ANPP P1]", header_compact)
        self.assertIn("§ Contre-indications", header_compact)

    def test_recursive_splitter_small_text(self):
        """Test that small text stays intact as a single chunk."""
        splitter = RecursiveSemanticSplitter(max_chars=500, overlap_chars=50)
        short_text = "Ceci est un court texte de posologie. Prendre 1 comprimé le matin."
        chunks = splitter.split_text(short_text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], short_text)

    def test_recursive_splitter_long_text_paragraphs(self):
        """Test that long text with paragraphs is split cleanly along paragraph boundaries."""
        splitter = RecursiveSemanticSplitter(max_chars=250, overlap_chars=40)
        p1 = "Paragraphe 1 : Posologie recommandée pour adulte. Ne pas dépasser 3000 mg par jour."
        p2 = "Paragraphe 2 : Chez l'insuffisant rénal, adapter l'intervalle entre prises à 8 heures minimum."
        p3 = "Paragraphe 3 : Population pédiatrique : présentation non adaptée chez l'enfant de moins de 50 kg."
        full_text = f"{p1}\n\n{p2}\n\n{p3}"

        chunks = splitter.split_text(full_text)
        self.assertGreaterEqual(len(chunks), 2)
        for c in chunks:
            self.assertLessEqual(len(c), 300)

    def test_chunk_serialization_and_qdrant_format(self):
        """Test to_dict, to_json, and to_qdrant_point formats."""
        chunk = DrugChunk(
            chunk_id="chk_test_01",
            text="[MÉDICAMENT: DOLIPRANE]\n\nPosologie test.",
            content="Posologie test.",
            header="[MÉDICAMENT: DOLIPRANE]",
            metadata={
                "drug_id": 1,
                "brand": "DOLIPRANE",
                "dci": "PARACÉTAMOL",
                "source": "anpp",
                "source_priority": 1,
                "section_category": "posology",
            },
        )
        d = chunk.to_dict()
        self.assertEqual(d["chunk_id"], "chk_test_01")
        self.assertIn("metadata", d)

        j = chunk.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["metadata"]["brand"], "DOLIPRANE")

        qp = chunk.to_qdrant_point()
        self.assertEqual(qp["id"], "chk_test_01")
        self.assertEqual(qp["payload"]["source"], "anpp")
        self.assertEqual(qp["payload"]["content"], "Posologie test.")


class TestChunkingWithOutputsData(unittest.TestCase):
    """
    Integration tests running the chunker directly against the curated
    monographs in data/outputs_data (40 DCIs, 989 JSON files).
    """

    def setUp(self):
        self.chunker = DrugChunker(ChunkingConfig(max_chunk_chars=1200, overlap_chars=150))
        self.sample_doliprane = DATA_OUTPUTS_DIR / "01_paracetamol" / "1_1" / "001_DOLIPRANE.json"

    def test_dossiers_discovery(self):
        """Verify discovery of the 40 target DCI dossiers in data/outputs_data."""
        dossiers = get_all_dossiers(DATA_OUTPUTS_DIR)
        self.assertEqual(len(dossiers), 40, "Outputs data must contain exactly 40 DCI dossiers")
        self.assertIn("01_paracetamol", dossiers)
        self.assertIn("02_ibuprofene", dossiers)
        self.assertIn("16_cefuroxime", dossiers)
        self.assertIn("40_methyldopa", dossiers)

    def test_anpp_monograph_json_canonical_question(self):
        """
        Verify chunking on official ANPP DOLIPRANE 1000 mg (001_DOLIPRANE.json).
        Validates the canonical benchmark question N1-01 criteria:
        1. 3000 mg/day normal maximum
        2. 4000 mg/day only on medical advice and patient >= 50 kg
        3. 4-hour minimum interval
        4. Verifiable ANPP RCP provenance
        """
        if not self.sample_doliprane.exists():
            self.skipTest(f"Doliprane file not found: {self.sample_doliprane}")

        # Chunk using chunk_file (auto-detects .json monograph)
        chunks = chunk_file(self.sample_doliprane)
        self.assertGreater(len(chunks), 0)

        # Find Posologie chunks
        posology_chunks = [c for c in chunks if c.metadata.get("section_category") == "posology"]
        self.assertGreater(len(posology_chunks), 0, "Doliprane posology chunks must be produced")

        # Verify canonical benchmark facts
        combined_posology = " ".join(c.content for c in posology_chunks)
        self.assertIn("3000 mg", combined_posology)
        self.assertIn("4000 mg", combined_posology)
        self.assertIn("4 heures", combined_posology)
        self.assertIn("50 kg", combined_posology)

        # Check metadata provenance
        sample = posology_chunks[0]
        self.assertEqual(sample.metadata["source"], "anpp")
        self.assertEqual(sample.metadata["source_priority"], 1)
        self.assertEqual(sample.metadata["doc_type"], "rcp")
        self.assertEqual(sample.metadata["brand"], "DOLIPRANE")
        self.assertEqual(sample.metadata["dci"], "PARACÉTAMOL")
        self.assertEqual(sample.metadata["dossier"], "01_paracetamol")
        self.assertEqual(sample.metadata["file_name"], "001_DOLIPRANE.json")
        self.assertIn("MÉDICAMENT: DOLIPRANE", sample.header)

    def test_patient_notice_monograph(self):
        """Verify chunking of patient notices in outputs_data."""
        # Find any notice file in outputs_data
        notices = []
        for p in sorted(DATA_OUTPUTS_DIR.glob("01_paracetamol/*/*.json")):
            with open(p, "r", encoding="utf-8") as f:
                if json.load(f).get("doc_type") == "notice":
                    notices.append(p)
                    break

        if not notices:
            self.skipTest("No notice document found in sample folder")

        chunks = chunk_file(notices[0])
        self.assertGreater(len(chunks), 0)
        self.assertEqual(chunks[0].metadata["doc_type"], "notice")

    def test_international_reference_monograph(self):
        """Verify chunking handles DailyMed / BDPM monographs in outputs_data (folder 3_3)."""
        ref_files = list(DATA_OUTPUTS_DIR.glob("16_cefuroxime/3_3/*.json"))
        if not ref_files:
            ref_files = list(DATA_OUTPUTS_DIR.glob("*/3_3/*.json"))

        if not ref_files:
            self.skipTest("No 3_3 reference file found")

        chunks = chunk_file(ref_files[0])
        self.assertGreater(len(chunks), 0)
        sample = chunks[0]
        self.assertIn(sample.metadata["source"], {"dailymed", "bdpm"})
        self.assertEqual(sample.metadata["source_priority"], 3)
        self.assertTrue(bool(sample.metadata["section_category"]))

    def test_directory_chunking_filtered_by_dossier(self):
        """Test streaming directory chunking filtered by dossier."""
        chunks = list(
            self.chunker.chunk_directory(
                DATA_OUTPUTS_DIR,
                dossier="01_paracetamol",
                max_docs=3,
            )
        )
        self.assertGreater(len(chunks), 0)
        for c in chunks:
            self.assertEqual(c.metadata["dossier"], "01_paracetamol")

    def test_export_and_stream(self):
        """Test streaming chunking and exporting to JSONL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "test_corpus_chunks.jsonl"
            # Stream chunks from first 2 monographs
            chunks = list(chunk_corpus(DATA_OUTPUTS_DIR, dossier="01_paracetamol", max_docs=2))
            self.assertGreater(len(chunks), 0)

            count = self.chunker.export_to_jsonl(chunks, out_file)
            self.assertEqual(count, len(chunks))
            self.assertTrue(out_file.exists())

            # Read back and verify valid JSON
            with open(out_file, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f]
            self.assertEqual(len(lines), count)

    def test_chunk_statistics(self):
        """Verify statistics computation on monographs from data/outputs_data."""
        chunks = chunk_file(self.sample_doliprane)
        stats = self.chunker.get_statistics(chunks)
        self.assertEqual(stats["total_chunks"], len(chunks))
        self.assertGreater(stats["avg_char_length"], 0)
        self.assertIn("anpp", stats["sources_breakdown"])
        self.assertIn("posology", stats["categories_breakdown"])


def run_standalone():
    """Runs tests and prints formatted summary."""
    print("=" * 70)
    print("PHARMEAZOR RAG CHUNKING ENGINE - DATA/OUTPUTS_DATA TEST SUITE")
    print("=" * 70)
    print(f"Data Source Directory: {DATA_OUTPUTS_DIR}")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestChunkingUnit))
    suite.addTests(loader.loadTestsFromTestCase(TestChunkingWithOutputsData))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print(f"SUCCESS: All {result.testsRun} tests passed perfectly on data/outputs_data!")
        # Print sample chunk statistics on real Doliprane monograph
        sample_path = DATA_OUTPUTS_DIR / "01_paracetamol" / "1_1" / "001_DOLIPRANE.json"
        if sample_path.exists():
            chunker = DrugChunker()
            chunks = chunk_file(sample_path)
            stats = chunker.get_statistics(chunks)
            print("-" * 70)
            print("SAMPLE STATISTICS - 001_DOLIPRANE.json (ANPP Official RCP):")
            print(f"  Total Chunks Generated : {stats['total_chunks']}")
            print(f"  Split Chunks Count     : {stats['split_chunks_count']}")
            print(f"  Average Chunk Length   : {stats['avg_char_length']} chars")
            print(f"  Min / Max Length       : {stats['min_char_length']} / {stats['max_char_length']} chars")
            print("  Clinical Categories Breakdown:")
            for cat, cnt in sorted(stats["categories_breakdown"].items(), key=lambda x: -x[1]):
                print(f"    - {cat:<24} : {cnt} chunks")
            print("-" * 70)
            sample_posology = [c for c in chunks if c.metadata.get("section_category") == "posology"]
            if sample_posology:
                print("SAMPLE POSOLOGY CHUNK (Contextual Header + Preview):")
                print(sample_posology[0].text[:450] + "\n...")
            print("-" * 70)
    else:
        print(f"FAILED: {len(result.failures)} failures, {len(result.errors)} errors.")
    print("=" * 70)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_standalone())
