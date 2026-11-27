from __future__ import annotations
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Augmentation.knowledge_graph.graph_builder import GraphBuilder

@dataclass
class ValidationIssue:
    severity: str         
    category: str         
    rule: str            
    message: str           
    entity_id: Optional[str] = None
    edge_key: Optional[str] = None


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




class GraphValidator:
    
    def __init__(self, builder: GraphBuilder):
        self.builder = builder
        self.graph = builder.graph
        self.report = ValidationReport()
    
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
        return self.report
        

    def _check_structural(self) -> None:
        
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            if u == v:
                self.report.add(ValidationIssue(
                    severity="ERROR",
                    category="STRUCTURAL",
                    rule="no_self_loops",
                    message=f"Self-loop detected: {u} -> {u}",
                    entity_id=u,
                    edge_key=f"{u}->{v}:{k}",
                ))

        node_ids = set(self.graph.nodes())
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            for nid, role in [(u, "source"), (v, "target")]:
                if nid not in node_ids:
                    self.report.add(ValidationIssue(
                        severity="ERROR",
                        category="STRUCTURAL",
                        rule="no_broken_refs",
                        message=f"Relation references missing node ({role}): {nid}",
                        edge_key=f"{u}->{v}:{k}",
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
                    severity="ERROR",
                    category="PROVENANCE",
                    rule="requires_evidence",
                    message=f"Clinical relation '{rtype}' lacks evidence_text",
                    edge_key=f"{u}->{v}:{k}",
                ))
            
            elif len(str(evidence).strip()) < 10:
                self.report.add(ValidationIssue(
                    severity="WARNING",
                    category="PROVENANCE",
                    rule="weak_evidence",
                    message=f"Evidence too short ({len(evidence)} chars) for '{rtype}'",
                    edge_key=f"{u}->{v}:{k}",
                ))


    def _check_consistency(self) -> None:
        from collections import defaultdict
        

        pair_map = defaultdict(set)
        pair_edges = defaultdict(list)
        
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            rtype = data.get("relation_type")
            pair_map[(u, v)].add(rtype)
            pair_edges[(u, v)].append(f"{u}->{v}:{k}")
        
        for (src, tgt), rtypes in pair_map.items():
            if "TREATS" in rtypes and "CONTRAINDICATED_FOR" in rtypes:
                self.report.add(ValidationIssue(
                    severity="ERROR",
                    category="CONSISTENCY",
                    rule="no_treats_vs_contra",
                    message=f"Contradiction: {src} both TREATS and CONTRAINDICATED_FOR {tgt}",
                    entity_id=src,
                ))

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            docs = data.get("source_docs") or []
            if len(docs) < 2:
                self.report.add(ValidationIssue(
                    severity="WARNING",
                    category="CONSISTENCY",
                    rule="single_source_relation",
                    message=f"Relation backed by only {len(docs)} source(s)",
                    edge_key=f"{u}->{v}:{k}",
                ))


    def _check_completeness(self) -> None:

        for nid in self.graph.nodes():
            if self.graph.degree(nid) == 0:
                self.report.add(ValidationIssue(
                    severity="WARNING",
                    category="COMPLETENESS",
                    rule="no_orphans",
                    message=f"Orphan entity (no relations): {nid}",
                    entity_id=nid,
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
                    severity="WARNING",
                    category="COMPLETENESS",
                    rule="drug_has_dci",
                    message=f"DRUG missing CONTAINS_ACTIVE_INGREDIENT: {nid}",
                    entity_id=nid,
                ))
            if "MANUFACTURED_BY" not in out_types:
                self.report.add(ValidationIssue(
                    severity="WARNING",
                    category="COMPLETENESS",
                    rule="drug_has_lab",
                    message=f"DRUG missing MANUFACTURED_BY: {nid}",
                    entity_id=nid,
                ))

    def _check_data_quality(self) -> None:
        for nid, attrs in self.graph.nodes(data=True):
            meta = attrs.get("metadata") or {}
            if meta.get("inferred_stub"):
                self.report.add(ValidationIssue(
                    severity="ERROR",
                    category="DATA_QUALITY",
                    rule="no_inferred_stubs",
                    message=f"Inferred stub (not extracted from text): {nid}",
                    entity_id=nid,
                ))

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            meta = data.get("metadata") or {}
            ev = meta.get("evidence_text")
            if isinstance(ev, str) and ev and not ev.strip():
                self.report.add(ValidationIssue(
                    severity="ERROR",
                    category="DATA_QUALITY",
                    rule="empty_evidence",
                    message="Evidence present but blank",
                    edge_key=f"{u}->{v}:{k}",
                ))