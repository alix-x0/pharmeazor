"""
Test Suite for Pharmeazor Knowledge Graph Relationship Extractor
================================================================
Tests entity and relationship extraction across clinical sections
using official monographs from data/outputs_data.

Run:
    python ai_api/Augmentation/knowledge_graph/test_relationship_extractor.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Augmentation.knowledge_graph.ontology import EntityType, RelationType
from ai_api.Augmentation.knowledge_graph.relationship_extractor import (
    DEFAULT_DATA_DIR,
    RelationshipExtractor,
)


class TestRelationshipExtractor(unittest.TestCase):

    def setUp(self):
        self.extractor = RelationshipExtractor()
        self.doliprane_path = DEFAULT_DATA_DIR / "01_paracetamol" / "1_1" / "001_DOLIPRANE.json"

    def test_doliprane_extraction(self):
        """Verify full entity and relationship extraction on official Doliprane RCP."""
        if not self.doliprane_path.exists():
            self.skipTest(f"File not found: {self.doliprane_path}")

        result = self.extractor.extract_from_file(self.doliprane_path)

        self.assertGreater(len(result.entities), 20, "Should extract numerous clinical entities")
        self.assertGreater(len(result.relations), 20, "Should extract numerous clinical relations")

        rel_types = {r.relation_type for r in result.relations}

        # Check essential clinical relation types
        self.assertIn(RelationType.CONTAINS_ACTIVE_INGREDIENT, rel_types)
        self.assertIn(RelationType.MANUFACTURED_BY, rel_types)
        self.assertIn(RelationType.TREATS, rel_types)
        self.assertIn(RelationType.INTERACTS_WITH, rel_types)
        self.assertIn(RelationType.HAS_ADVERSE_EFFECT, rel_types)
        self.assertIn(RelationType.REQUIRES_PRECAUTION_FOR, rel_types)

        # Check specific triples
        active_ing_rel = next(
            r for r in result.relations if r.relation_type == RelationType.CONTAINS_ACTIVE_INGREDIENT
        )
        self.assertEqual(active_ing_rel.source_id, "drug_doliprane")
        self.assertEqual(active_ing_rel.target_id, "active_ingredient_paracetamol")

        lab_rel = next(
            r for r in result.relations if r.relation_type == RelationType.MANUFACTURED_BY
        )
        self.assertEqual(lab_rel.source_id, "drug_doliprane")
        self.assertEqual(lab_rel.target_id, "laboratory_propharmal_spa")

        # Check interactions extracted
        interactions = [
            r for r in result.relations if r.relation_type == RelationType.INTERACTS_WITH
        ]
        self.assertGreater(len(interactions), 0)
        target_ids = {r.target_id for r in interactions}
        self.assertTrue(
            any("antivitamine" in tid for tid in target_ids),
            "Should extract interaction with Antivitamines K",
        )

    def test_corpus_streaming(self):
        """Test streaming extraction from first 2 monographs."""
        result = self.extractor.extract_from_corpus(
            data_dir=DEFAULT_DATA_DIR,
            dossiers=["01_paracetamol"],
            max_docs=2,
        )
        self.assertGreater(len(result.relations), 0)
        self.assertGreater(len(result.entities), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
