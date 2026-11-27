from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Augmentation.knowledge_graph.graph_builder import (
    DEFAULT_GRAPH_PATH, 
    GraphBuilder,
)
from ai_api.Augmentation.knowledge_graph.ontology import EntityType, RelationType,KGEntity,KGRelation


@dataclass
class ValidationIssue:
    severity: str          
    category: str          
    rule: str
    message: str
    entity_id: Optional[str] = None
    edge_key: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "rule": self.rule,
            "message": self.message,
            "entity_id": self.entity_id,
            "edge_key": self.edge_key,
            "details": self.details,
        }


@dataclass
class ValidationReport:
    total_entities: int = 0
    total_relations: int = 0
    issues: List[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def count(self) -> Dict[str, int]:
        counts = {"ERROR": 0, "WARNING": 0, "INFO": 0}
        for i in self.issues:
            counts[i.severity] = counts.get(i.severity, 0) + 1
        return counts

    def is_valid(self) -> bool:
        return len([i for i in self.issues if i.severity == "ERROR"]) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_entities": self.total_entities,
            "total_relations": self.total_relations,
            "summary": self.count(),
            "is_valid": self.is_valid(),
            "issues": [i.to_dict() for i in self.issues],
        }

    def print_summary(self) -> None:
        c = self.count()
        print("=" * 72)
        print("GRAPH VALIDATION REPORT")
        print("=" * 72)
        print(f"Total Entities  : {self.total_entities}")
        print(f"Total Relations : {self.total_relations}")
        print(f"Errors          : {c['ERROR']}")
        print(f"Warnings        : {c['WARNING']}")
        print(f"Infos           : {c['INFO']}")
        print(f"Graph Valid     : {'✅ YES' if self.is_valid() else '❌ NO'}")
        print("=" * 72)

        if self.issues:
            print("\n--- Issues by Category ---")
            cats: Dict[str, List[ValidationIssue]] = defaultdict(list)
            for i in self.issues:
                cats[i.category].append(i)
            for cat, items in cats.items():
                print(f"\n[{cat}] ({len(items)} issues)")
                for issue in items[:5]:
                    print(f"  [{issue.severity}] {issue.rule}: {issue.message}")
                if len(items) > 5:
                    print(f"  ... and {len(items) - 5} more")




class GraphValidator:

    def __init__(self, builder: GraphBuilder):
        self.builder = builder
        self.graph = builder.graph
        self.report = ValidationReport()
    @classmethod
    def validate_pre_build(
        cls,
        entities: List[KGEntity],
        relations: List[KGRelation],
    ) -> ValidationReport:

        temp_builder = GraphBuilder()


        for e in entities:
            temp_builder.add_entity(e)
        for r in relations:
            temp_builder.add_relation(r)


        validator = cls(temp_builder)
        return validator.validate()

    def validate(self) -> ValidationReport:
        self.report = ValidationReport(
            total_entities=self.graph.number_of_nodes(),
            total_relations=self.graph.number_of_edges(),
        )

        self._check_structural()
        self._check_provenance()
        self._check_consistency()
        self._check_completeness()
        self._check_data_quality()
        self._check_metadata()
        self._check_classification()
        self._check_duplicates()

        return self.report


    def _check_structural(self) -> None:
       

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            if u == v:
                self.report.add(ValidationIssue(
                    severity="ERROR", category="STRUCTURAL", rule="no_self_loops",
                    message=f"Self-loop: {u} -> {u}",
                    entity_id=u, edge_key=f"{u}->{v}:{k}",
                ))


        node_ids = set(self.graph.nodes())
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            for nid, role in [(u, "source"), (v, "target")]:
                if nid not in node_ids:
                    self.report.add(ValidationIssue(
                        severity="ERROR", category="STRUCTURAL", rule="no_broken_refs",
                        message=f"Missing node ({role}): {nid}",
                        edge_key=f"{u}->{v}:{k}",
                    ))

 
        seen_ids: Set[str] = set()
        for nid in self.graph.nodes():
            if nid in seen_ids:
                self.report.add(ValidationIssue(
                    severity="ERROR", category="STRUCTURAL", rule="no_duplicate_ids",
                    message=f"Duplicate ID: {nid}", entity_id=nid,
                ))
            seen_ids.add(nid)

        valid_rel_types = {rt.value for rt in RelationType}
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            rtype = data.get("relation_type")
            if rtype not in valid_rel_types:
                self.report.add(ValidationIssue(
                    severity="ERROR", category="STRUCTURAL", rule="invalid_relation_type",
                    message=f"Invalid relation_type: '{rtype}'",
                    edge_key=f"{u}->{v}:{k}",
                ))


        for nid, attrs in self.graph.nodes(data=True):
            if not nid or not str(nid).strip():
                self.report.add(ValidationIssue(
                    severity="ERROR", category="STRUCTURAL", rule="empty_entity_id",
                    message="Entity has empty ID", entity_id=nid,
                ))
            if not attrs.get("name") or not str(attrs.get("name")).strip():
                self.report.add(ValidationIssue(
                    severity="ERROR", category="STRUCTURAL", rule="empty_entity_name",
                    message=f"Entity has empty name: {nid}", entity_id=nid,
                ))


    def _check_provenance(self) -> None:

        STRUCTURAL_RELS = {
            "CONTAINS_ACTIVE_INGREDIENT",
            "MANUFACTURED_BY",
            "HAS_DOSAGE_FORM",
        }

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            rtype = data.get("relation_type")
            if rtype in STRUCTURAL_RELS:
                continue

            meta = data.get("metadata") or {}
            evidence = meta.get("evidence_text")


            if not evidence or not str(evidence).strip():
                self.report.add(ValidationIssue(
                    severity="ERROR", category="PROVENANCE", rule="requires_evidence",
                    message=f"'{rtype}' lacks evidence_text",
                    edge_key=f"{u}->{v}:{k}",
                ))

            elif len(str(evidence).strip()) < 10:
                self.report.add(ValidationIssue(
                    severity="WARNING", category="PROVENANCE", rule="weak_evidence",
                    message=f"Evidence too short ({len(evidence)} chars) for '{rtype}'",
                    edge_key=f"{u}->{v}:{k}",
                ))

            if not data.get("source_doc") and not data.get("source_docs"):
                self.report.add(ValidationIssue(
                    severity="WARNING", category="PROVENANCE", rule="missing_source_doc",
                    message=f"Relation missing source_doc: {rtype}",
                    edge_key=f"{u}->{v}:{k}",
                ))

    def _check_consistency(self) -> None:

        pair_map: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            pair_map[(u, v)].add(data.get("relation_type"))

        for (src, tgt), rtypes in pair_map.items():
            if "TREATS" in rtypes and "CONTRAINDICATED_FOR" in rtypes:
                self.report.add(ValidationIssue(
                    severity="ERROR", category="CONSISTENCY", rule="no_treats_vs_contra",
                    message=f"Contradiction: {src} both TREATS and CONTRAINDICATED_FOR {tgt}",
                    entity_id=src,
                ))

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            docs = data.get("source_docs") or []
            if len(docs) < 2:
                self.report.add(ValidationIssue(
                    severity="WARNING", category="CONSISTENCY", rule="single_source_relation",
                    message=f"Relation backed by only {len(docs)} source(s)",
                    edge_key=f"{u}->{v}:{k}",
                ))

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            if data.get("relation_type") == "INTERACTS_WITH" and u == v:
                self.report.add(ValidationIssue(
                    severity="ERROR", category="CONSISTENCY", rule="no_self_interaction",
                    message=f"Self-interaction: {u} interacts with itself",
                    entity_id=u,
                ))


    def _check_completeness(self) -> None:

        for nid in self.graph.nodes():
            if self.graph.degree(nid) == 0:
                self.report.add(ValidationIssue(
                    severity="WARNING", category="COMPLETENESS", rule="no_orphans",
                    message=f"Orphan entity: {nid}", entity_id=nid,
                ))

        for nid, attrs in self.graph.nodes(data=True):
            if attrs.get("entity_type") != "DRUG":
                continue
            out_types = {
                d.get("relation_type")
                for _, _, _, d in self.graph.out_edges(nid, keys=True, data=True)
            }
            if "CONTAINS_ACTIVE_INGREDIENT" not in out_types:
                self.report.add(ValidationIssue(
                    severity="WARNING", category="COMPLETENESS", rule="drug_has_dci",
                    message=f"DRUG missing DCI: {nid}", entity_id=nid,
                ))
            if "MANUFACTURED_BY" not in out_types:
                self.report.add(ValidationIssue(
                    severity="WARNING", category="COMPLETENESS", rule="drug_has_lab",
                    message=f"DRUG missing LAB: {nid}", entity_id=nid,
                ))


    def _check_data_quality(self) -> None:
        
        for nid, attrs in self.graph.nodes(data=True):
            meta = attrs.get("metadata") or {}
            if meta.get("inferred_stub"):
                self.report.add(ValidationIssue(
                    severity="ERROR", category="DATA_QUALITY", rule="no_inferred_stubs",
                    message=f"Inferred stub: {nid}", entity_id=nid,
                ))

        
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            meta = data.get("metadata") or {}
            ev = meta.get("evidence_text")
            if isinstance(ev, str) and ev and not ev.strip():
                self.report.add(ValidationIssue(
                    severity="ERROR", category="DATA_QUALITY", rule="empty_evidence",
                    message="Evidence blank", edge_key=f"{u}->{v}:{k}",
                ))
            conf = data.get("confidence")
            if conf is not None and not (0.0 <= float(conf) <= 1.0):
                self.report.add(ValidationIssue(
                    severity="ERROR", category="DATA_QUALITY", rule="invalid_confidence",
                    message=f"Confidence out of [0,1]: {conf}",
                    edge_key=f"{u}->{v}:{k}",
                ))


    def _check_metadata(self) -> None:
        
        for nid, attrs in self.graph.nodes(data=True):
            if not attrs.get("collection_date"):
                self.report.add(ValidationIssue(
                    severity="WARNING", category="METADATA", rule="missing_collection_date",
                    message=f"Missing collection_date: {nid}", entity_id=nid,
                ))

        
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            if data.get("source_authority") is None:
                self.report.add(ValidationIssue(
                    severity="WARNING", category="METADATA", rule="missing_source_authority",
                    message=f"Missing source_authority: {u}->{v}",
                    edge_key=f"{u}->{v}:{k}",
                ))


    def _check_classification(self) -> None:
  
        for nid, attrs in self.graph.nodes(data=True):
            if attrs.get("entity_type") != "DRUG":
                continue
            out_types = {
                d.get("relation_type")
                for _, _, _, d in self.graph.out_edges(nid, keys=True, data=True)
            }
            if "HAS_ATC_CLASS" not in out_types:
                self.report.add(ValidationIssue(
                    severity="WARNING", category="CLASSIFICATION", rule="drug_has_atc",
                    message=f"DRUG missing ATC_CLASS: {nid}", entity_id=nid,
                ))
            if "HAS_THERAPEUTIC_CLASS" not in out_types:
                self.report.add(ValidationIssue(
                    severity="WARNING", category="CLASSIFICATION", rule="drug_has_therapeutic_class",
                    message=f"DRUG missing THERAPEUTIC_CLASS: {nid}", entity_id=nid,
                ))

   
    def _check_duplicates(self) -> None:

        seen: Dict[str, str] = {}
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            rtype = data.get("relation_type")
            key = f"{u}->{v}:{rtype}"
            if key in seen:
                self.report.add(ValidationIssue(
                    severity="WARNING", category="DUPLICATES", rule="duplicate_relation",
                    message=f"Duplicate relation: {key}",
                    edge_key=f"{u}->{v}:{k}",
                ))
            seen[key] = f"{u}->{v}:{k}"

