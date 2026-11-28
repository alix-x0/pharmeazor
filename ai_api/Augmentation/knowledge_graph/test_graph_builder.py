"""
Test Suite for Pharmeazor Knowledge Graph Builder
=================================================
Verifies entity/relation ingestion, deduplication, provenance merging,
lookup indices, k-hop subgraph extraction, GraphRAG context formatting,
JSON/GraphML persistence, and integration with the curated corpus.

Run:
    python ai_api/Augmentation/knowledge_graph/test_graph_builder.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import networkx as nx

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Augmentation.knowledge_graph.graph_builder import (
    GraphBuilder,
    build_knowledge_graph,
    load_knowledge_graph,
)
from ai_api.Augmentation.knowledge_graph.graph_validator import GraphValidator
from ai_api.Augmentation.knowledge_graph.ontology import (
    EntityType,
    KGEntity,
    KGRelation,
    RelationType,
)
from ai_api.Augmentation.knowledge_graph.relationship_extractor import DEFAULT_DATA_DIR
from ai_api.Retrieval.chunking import DrugChunk


class TestGraphBuilderUnit(unittest.TestCase):
    """Unit tests for GraphBuilder indexing, merging, traversal, and serialization."""

    def setUp(self):
        self.builder = GraphBuilder()
        self.drug = KGEntity(
            id="drug_doliprane",
            name="DOLIPRANE",
            entity_type=EntityType.DRUG,
            aliases=["doliprane", "DOLIPRANE"],
            metadata={"source": "anpp", "drug_id": 1},
        )
        self.dci = KGEntity(
            id="active_ingredient_paracetamol",
            name="PARACÉTAMOL",
            entity_type=EntityType.ACTIVE_INGREDIENT,
            aliases=["paracetamol", "PARACÉTAMOL"],
            metadata={"drug_id": 1},
        )
        self.pop = KGEntity(
            id="population_grossesse",
            name="Femmes enceintes (Grossesse)",
            entity_type=EntityType.POPULATION,
        )

    def test_entity_merging_and_metadata_accumulation(self):
        self.builder.add_entity(self.drug)
        duplicate = KGEntity(
            id="drug_doliprane",
            name="DOLIPRANE",
            entity_type=EntityType.DRUG,
            aliases=["Doliprane 1000 mg"],
            metadata={"source": "pharmnet", "drug_id": 2},
        )
        merged = self.builder.add_entity(duplicate)

        self.assertEqual(self.builder.graph.number_of_nodes(), 1)
        self.assertIn("Doliprane 1000 mg", merged.aliases)
        self.assertEqual(set(merged.metadata["sources"]), {"anpp", "pharmnet"})
        self.assertEqual(self.builder.stats.entities_added, 1)
        self.assertEqual(self.builder.stats.entities_merged, 1)

    def test_multiedge_distinct_relations_and_provenance_merging(self):
        self.builder.add_entity(self.drug)
        self.builder.add_entity(self.pop)

        r1 = KGRelation(
            source_id=self.drug.id,
            target_id=self.pop.id,
            relation_type=RelationType.REQUIRES_PRECAUTION_FOR,
            description="Précaution grossesse",
            source_doc="doc_a.json",
            confidence=0.8,
        )
        r2 = KGRelation(
            source_id=self.drug.id,
            target_id=self.pop.id,
            relation_type=RelationType.CONTRAINDICATED_FOR,
            description="Contre-indiqué au 3e trimestre",
            source_doc="doc_b.json",
            confidence=0.9,
        )
        r1_dup = KGRelation(
            source_id=self.drug.id,
            target_id=self.pop.id,
            relation_type=RelationType.REQUIRES_PRECAUTION_FOR,
            description="Précaution grossesse détaillée",
            source_doc="doc_c.json",
            confidence=0.95,
        )

        self.builder.add_relation(r1)
        self.builder.add_relation(r2)
        self.builder.add_relation(r1_dup)

        # Two distinct edge keys between the same node pair
        self.assertEqual(self.builder.graph.number_of_edges(), 2)
        rels = self.builder.get_relations(source_id=self.drug.id, target_id=self.pop.id)
        self.assertEqual(len(rels), 2)

        prec = next(r for r in rels if r.relation_type == RelationType.REQUIRES_PRECAUTION_FOR)
        self.assertEqual(prec.confidence, 0.95)
        self.assertEqual(prec.description, "Précaution grossesse détaillée")
        self.assertEqual(prec.metadata["source_docs"], ["doc_a.json", "doc_c.json"])

    def test_confidence_threshold_filtering(self):
        strict_builder = GraphBuilder(confidence_threshold=0.85)
        strict_builder.add_entity(self.drug)
        strict_builder.add_entity(self.dci)

        low_rel = KGRelation(
            source_id=self.drug.id,
            target_id=self.dci.id,
            relation_type=RelationType.CONTAINS_ACTIVE_INGREDIENT,
            confidence=0.5,
        )
        high_rel = KGRelation(
            source_id=self.drug.id,
            target_id=self.dci.id,
            relation_type=RelationType.CONTAINS_ACTIVE_INGREDIENT,
            confidence=0.95,
        )

        self.assertFalse(strict_builder.add_relation(low_rel))
        self.assertTrue(strict_builder.add_relation(high_rel))
        self.assertEqual(strict_builder.graph.number_of_edges(), 1)
        self.assertEqual(strict_builder.stats.relations_skipped_low_confidence, 1)

    def test_find_entities_and_query_extraction(self):
        self.builder.add_entity(self.drug)
        self.builder.add_entity(self.dci)

        # Diacritic-insensitive lookup
        found = self.builder.find_entities("paracetamol", entity_type=EntityType.ACTIVE_INGREDIENT)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].id, self.dci.id)

        # Canonical smoke question N1-01 entity extraction
        question = (
            "Chez un adulte de 60 kg, quelle est la dose journalière maximale "
            "de DOLIPRANE 1000 mg en règle générale ?"
        )
        extracted = self.builder.extract_entities_from_query(question)
        self.assertTrue(any(e.id == "drug_doliprane" for e in extracted))

    def test_save_load_roundtrip_and_graphml(self):
        self.builder.add_entity(self.drug)
        self.builder.add_entity(self.dci)
        self.builder.add_relation(
            KGRelation(
                source_id=self.drug.id,
                target_id=self.dci.id,
                relation_type=RelationType.CONTAINS_ACTIVE_INGREDIENT,
                description="DOLIPRANE contient PARACÉTAMOL",
                source_doc="001_DOLIPRANE.json",
                confidence=1.0,
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "kg.json"
            graphml_path = Path(tmpdir) / "kg.graphml"

            self.builder.save(json_path)
            loaded = load_knowledge_graph(json_path)

            self.assertEqual(loaded.graph.number_of_nodes(), 2)
            self.assertEqual(loaded.graph.number_of_edges(), 1)
            self.assertIsNotNone(loaded.get_entity("drug_doliprane"))
            self.assertEqual(len(loaded.find_entities("paracetamol")), 1)

            loaded.export_graphml(graphml_path)
            self.assertTrue(graphml_path.exists())
            gml = nx.read_graphml(str(graphml_path))
            self.assertEqual(gml.number_of_nodes(), 2)

    def test_build_from_chunk_preserves_chunk_provenance(self):
        chunk = DrugChunk(
            chunk_id="chk_anpp_posologie_test",
            text="",
            content="La dose maximale journalière ne doit pas dépasser 3 g.",
            header="",
            metadata={
                "brand": "DOLIPRANE",
                "dci": "PARACÉTAMOL",
                "source": "anpp",
                "doc_type": "rcp",
                "dossier": "01_paracetamol",
                "file_name": "001_DOLIPRANE.json",
                "section_key": "posologie",
                "section_number": "4.2",
                "section_title": "Posologie",
            },
        )

        builder = GraphBuilder()
        builder.build_from_chunks([chunk])

        self.assertEqual(builder.stats.chunks_processed, 1)
        self.assertEqual(builder.stats.documents_processed, 1)
        relation = next(
            rel
            for rel in builder.get_relations()
            if rel.relation_type == RelationType.HAS_MAX_DOSE
        )
        self.assertEqual(relation.source_chunk_id, chunk.chunk_id)
        self.assertEqual(relation.source_doc, "01_paracetamol/001_DOLIPRANE.json")
        self.assertEqual(
            relation.metadata["evidence_text"],
            "La dose maximale journalière ne doit pas dépasser 3 g.",
        )
        self.assertTrue(GraphValidator(builder).validate().is_valid())


class TestGraphBuilderCorpusIntegration(unittest.TestCase):
    """Integration tests against real pharmaceutical monographs in data/outputs_data."""

    def setUp(self):
        self.doliprane_path = DEFAULT_DATA_DIR / "01_paracetamol" / "1_1" / "001_DOLIPRANE.json"

    def test_build_from_doliprane_and_subgraph_retrieval(self):
        if not self.doliprane_path.exists():
            self.skipTest(f"File not found: {self.doliprane_path}")

        builder = GraphBuilder()
        builder.build_from_files([self.doliprane_path])

        stats = builder.get_statistics()
        self.assertGreater(stats["total_nodes"], 20)
        self.assertGreater(stats["total_edges"], 20)
        self.assertEqual(stats["build_stats"]["documents_processed"], 1)

        # Neighbor traversal
        interactions = builder.get_neighbors(
            "drug_doliprane",
            relation_types=[RelationType.INTERACTS_WITH],
            direction="out",
        )
        self.assertGreater(len(interactions), 0)
        self.assertTrue(
            any("antivitamine" in ent.id for _rel, ent in interactions),
            "Should traverse INTERACTS_WITH to Antivitamines K",
        )

        # Subgraph + GraphRAG formatting
        sub = builder.get_subgraph(
            seed_ids=["drug_doliprane"],
            max_hops=1,
            relation_types=[RelationType.HAS_MAX_DOSE, RelationType.CONTAINS_ACTIVE_INGREDIENT],
            max_nodes=25,
        )
        self.assertGreater(sub.number_of_edges(), 0)
        context = builder.format_subgraph_context(sub)
        self.assertIn("DOLIPRANE", context)
        self.assertIn("001_DOLIPRANE.json", context)

        # Drug summary
        summary = builder.get_drug_summary("DOLIPRANE")
        self.assertTrue(summary["found"])
        self.assertIn("CONTAINS_ACTIVE_INGREDIENT", summary["relations_by_type"])
        self.assertIn("HAS_MAX_DOSE", summary["relations_by_type"])

    def test_chunked_doliprane_has_no_inferred_severe_hepatic_stub(self):
        if not self.doliprane_path.exists():
            self.skipTest(f"File not found: {self.doliprane_path}")

        builder = GraphBuilder()
        builder.build_from_chunked_corpus(
            data_dir=DEFAULT_DATA_DIR,
            dossier="01_paracetamol",
            sources=["anpp"],
            max_docs=1,
        )

        entity = builder.graph.nodes["contraindication_insuffisance_hepatocellulaire_severe"]
        self.assertFalse(entity["metadata"].get("inferred_stub"))

    def test_build_from_corpus_subset(self):
        if not DEFAULT_DATA_DIR.exists():
            self.skipTest(f"Data dir not found: {DEFAULT_DATA_DIR}")

        builder = build_knowledge_graph(
            data_dir=DEFAULT_DATA_DIR,
            dossiers=["01_paracetamol"],
            sources=["anpp"],
            max_docs=5,
        )
        stats = builder.get_statistics()
        self.assertEqual(stats["build_stats"]["documents_processed"], 5)
        self.assertGreater(stats["total_nodes"], 10)
        self.assertGreater(stats["total_edges"], 10)

        # Verify shared active ingredient hub links multiple drugs
        paracetamol_in = builder.get_neighbors(
            "active_ingredient_paracetamol",
            relation_types=[RelationType.CONTAINS_ACTIVE_INGREDIENT],
            direction="in",
        )
        self.assertGreaterEqual(len(paracetamol_in), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
