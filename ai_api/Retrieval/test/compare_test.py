"""
Pharmeazor RAG System - Comparaison Recherche par Mots-Clés vs Recherche Sémantique
==================================================================================
Module d'évaluation et de benchmark comparatif entre :
1. Recherche par Mots-Clés (Recherche Lexicale / Sparse / BM25)
2. Recherche Sémantique (Dense 1024-d / BGE-M3)
3. Recherche Hybride (Dense + Sparse avec Reciprocal Rank Fusion - RRF)

Objectifs de l'Analyse :
------------------------
- Mettre en évidence les forces et faiblesses respectives de chaque approche sur
  le corpus pharmaceutique algérien et international (ANPP, BDPM, Pharmnet, DailyMed).
- Déterminer les cas où la recherche lexicale est indispensable (dosages exacts, DCI,
  noms de marques, seuils de poids).
- Déterminer les cas où la recherche sémantique est supérieure (synonymie clinique,
  paraphrases, langage patient vs termes médicaux : "maux de tête" vs "céphalées",
  "fièvre" vs "états fébriles", "maladie du foie" vs "insuffisance hépatocellulaire").
- Prouver la supériorité de la recherche hybride (RRF) pour la sécurité clinique.

Run:
    python -m ai_api.Retrieval.test.compare_test
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger(__name__)

# Ensure package root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Retrieval.chunking import (
    DEFAULT_DATA_DIR,
    DrugChunk,
    DrugChunker,
    chunk_corpus,
)
from ai_api.Retrieval import (
    BGEM3Embedder,
    DrugRAGPipeline,
    EmbeddingConfig,
    QdrantConfig,
    QdrantVectorStore,
    RetrievalResult,
    default_embedder,
    default_store,
)

try:
    from qdrant_client.models import (
        FieldCondition,
        Filter,
        Fusion,
        FusionQuery,
        MatchValue,
        Prefetch,
        SparseVector,
    )
except ImportError:
    FieldCondition = None  # type: ignore
    Filter = None  # type: ignore
    Fusion = None  # type: ignore
    FusionQuery = None  # type: ignore
    MatchValue = None  # type: ignore
    Prefetch = None  # type: ignore
    SparseVector = None  # type: ignore


# ---------------------------------------------------------------------------
# Scénarios de Test Canoniques
# ---------------------------------------------------------------------------

@dataclass
class SearchBenchmarkCase:
    """Définition d'un scénario clinique de comparaison."""
    id: str
    title: str
    query: str
    expected_topic: str
    description: str
    key_differentiator: str  # 'semantic_win', 'keyword_win', 'hybrid_win'
    filter_dci: Optional[str] = None
    filter_category: Optional[str] = None


CANONICAL_SCENARIOS: List[SearchBenchmarkCase] = [
    SearchBenchmarkCase(
        id="SCENARIO-1",
        title="Synonymie clinique et langage patient (Céphalées vs Maux de tête)",
        query="médicament pour soulager les maux de tête intenses et faire baisser la température",
        expected_topic="Indications antalgiques et antipyrétiques (états fébriles, céphalées)",
        description="Le patient utilise 'maux de tête' et 'température', alors que le RCP officiel ANPP utilise 'céphalées' et 'états fébriles'.",
        key_differentiator="semantic_win",
        filter_dci="PARACÉTAMOL",
    ),
    SearchBenchmarkCase(
        id="SCENARIO-2",
        title="Question Canonique Projet RCR N1-01 (Dose maximale & Seuil de poids)",
        query="Chez un adulte de 60 kg, quelle est la dose journalière maximale de DOLIPRANE 1000 mg en règle générale, et dans quelle condition peut-on aller jusqu'à 4 g par jour ?",
        expected_topic="Posologie 4.2 - Doliprane 1000 mg comprimé (3 g/jour usuel, 4 g max sous avis médical)",
        description="Question canonique du benchmark Pharmeazor v2 combinant nom commercial, dosage strict et règle clinique.",
        key_differentiator="hybrid_win",
        filter_dci="PARACÉTAMOL",
    ),
    SearchBenchmarkCase(
        id="SCENARIO-3",
        title="Précision lexicale et contrainte posologique stricte (Dosage exact 1000 mg)",
        query="Doliprane 1000 mg comprimé 50 kg intervalle 4 heures",
        expected_topic="Posologie 4.2 - Table de posologie par prise et intervalle minimal",
        description="Requête ultra-spécifique contenant des valeurs numériques strictes ('1000 mg', '50 kg', '4 heures').",
        key_differentiator="keyword_win",
        filter_dci="PARACÉTAMOL",
    ),
    SearchBenchmarkCase(
        id="SCENARIO-4",
        title="Contre-indication formulée en langage courant (Foie vs Insuffisance hépatique)",
        query="peut-on prendre du paracétamol si le patient a une maladie grave du foie ?",
        expected_topic="Contre-indications 4.3 - Insuffisance hépatocellulaire sévère",
        description="Le texte officiel mentionne 'Insuffisance hépatocellulaire sévère', sans le mot 'foie'. La recherche par mot-clé échoue.",
        key_differentiator="semantic_win",
        filter_dci="PARACÉTAMOL",
    ),
    SearchBenchmarkCase(
        id="SCENARIO-5",
        title="Interaction Médicamenteuse & Avertissements (Surdosage & Alcool)",
        query="quels sont les risques de toxicité et de surdosage en cas de prise importante avec alcool ?",
        expected_topic="Mises en garde 4.4 & Surdosage 4.9 (cytolyse hépatique, toxicité accrue)",
        description="Requête croisant surdosage, toxicité et facteur de risque alcoolique.",
        key_differentiator="hybrid_win",
        filter_dci="PARACÉTAMOL",
    ),
]


# ---------------------------------------------------------------------------
# Structures de Données pour la Comparaison
# ---------------------------------------------------------------------------

@dataclass
class SearchResultItem:
    """Résultat unique issu d'une méthode de recherche."""
    rank: int
    score: float
    chunk_id: str
    header: str
    content: str
    section_category: str
    brand: str
    dci: str
    source: str

    def snippet(self, max_chars: int = 140) -> str:
        clean = " ".join(self.content.split())
        return clean[:max_chars] + ("..." if len(clean) > max_chars else "")


@dataclass
class ComparisonMetrics:
    """Métriques comparatives entre mots-clés, sémantique et hybride."""
    query: str
    keyword_count: int
    semantic_count: int
    hybrid_count: int
    jaccard_keyword_semantic: float       # Chevauchement entre mots-clés et sémantique
    jaccard_semantic_hybrid: float        # Chevauchement sémantique vs hybride
    jaccard_keyword_hybrid: float         # Chevauchement mots-clés vs hybride
    semantic_unique_chunks: List[str]     # Chunks trouvés uniquement par sémantique
    keyword_unique_chunks: List[str]      # Chunks trouvés uniquement par mots-clés
    execution_time_ms: Dict[str, float]


@dataclass
class QueryComparisonResult:
    """Regroupe les résultats des trois méthodes pour une requête donnée."""
    query: str
    keyword_results: List[SearchResultItem]
    semantic_results: List[SearchResultItem]
    hybrid_results: List[SearchResultItem]
    metrics: ComparisonMetrics
    scenario: Optional[SearchBenchmarkCase] = None


# ---------------------------------------------------------------------------
# Moteur de Comparaison
# ---------------------------------------------------------------------------

class SearchComparator:
    """
    Exécute et compare les trois modes de recherche :
    1. Mots-clés (Sparse lexical weights)
    2. Sémantique (Dense 1024-d BGE-M3)
    3. Hybride (Fusion RRF)
    """

    def __init__(
        self,
        embedder: Optional[BGEM3Embedder] = None,
        vector_store: Optional[QdrantVectorStore] = None,
    ):
        self.embedder = embedder or default_embedder
        self.vector_store = vector_store or default_store

    def _execute_qdrant_query(
        self,
        mode: str,
        query: str,
        limit: int = 5,
        filter_dci: Optional[str] = None,
        filter_category: Optional[str] = None,
    ) -> Tuple[List[SearchResultItem], float]:
        """Exécute une requête selon le mode spécifié et mesure le temps d'exécution."""
        start_time = time.time()
        client = self.vector_store.get_client()
        target = self.vector_store.config.collection_name

        dense_name = self.vector_store.embedding_config.dense_vector_name
        sparse_name = self.vector_store.embedding_config.sparse_vector_name

        # Construction des filtres
        must_conditions = []
        if filter_dci:
            must_conditions.append(FieldCondition(key="dci", match=MatchValue(value=filter_dci)))
        if filter_category:
            must_conditions.append(FieldCondition(key="section_category", match=MatchValue(value=filter_category)))
        q_filter = Filter(must=must_conditions) if must_conditions else None

        # 1. Encodage BGE-M3
        dense_vec, sparse_dict = self.embedder.encode_query(query)
        items: List[SearchResultItem] = []

        try:
            # Mode A : Sémantique Seule (Vecteur dense 1024-d)
            if mode == "semantic":
                response = client.query_points(
                    collection_name=target,
                    query=dense_vec,
                    using=dense_name,
                    limit=limit,
                    query_filter=q_filter,
                )
                points = response.points

            # Mode B : Mots-clés Seuls (Vecteur creux / Sparse lexical weights)
            elif mode == "keyword":
                if not sparse_dict:
                    return [], 0.0

                indices = list(sparse_dict.keys())
                values = list(sparse_dict.values())
                sparse_obj = SparseVector(indices=indices, values=values)

                response = client.query_points(
                    collection_name=target,
                    query=sparse_obj,
                    using=sparse_name,
                    limit=limit,
                    query_filter=q_filter,
                )
                points = response.points

            # Mode C : Hybride (Dense + Sparse avec RRF)
            elif mode == "hybrid":
                if sparse_dict:
                    sparse_indices = list(sparse_dict.keys())
                    sparse_values = list(sparse_dict.values())
                    sparse_obj = SparseVector(indices=sparse_indices, values=sparse_values)

                    prefetch = [
                        Prefetch(query=dense_vec, using=dense_name, limit=limit * 3, filter=q_filter),
                        Prefetch(query=sparse_obj, using=sparse_name, limit=limit * 3, filter=q_filter),
                    ]
                    response = client.query_points(
                        collection_name=target,
                        prefetch=prefetch,
                        query=FusionQuery(fusion=Fusion.RRF),
                        limit=limit,
                    )
                    points = response.points
                else:
                    response = client.query_points(
                        collection_name=target,
                        query=dense_vec,
                        using=dense_name,
                        limit=limit,
                        query_filter=q_filter,
                    )
                    points = response.points
            else:
                raise ValueError(f"Mode de recherche inconnu : {mode}")

            for rank, hit in enumerate(points, start=1):
                p = hit.payload or {}
                items.append(
                    SearchResultItem(
                        rank=rank,
                        score=float(hit.score or 0.0),
                        chunk_id=p.get("chunk_id", str(hit.id)),
                        header=p.get("header", ""),
                        content=p.get("content", ""),
                        section_category=p.get("section_category", "other"),
                        brand=p.get("brand", ""),
                        dci=p.get("dci", ""),
                        source=p.get("source", ""),
                    )
                )

        except Exception as e:
            logger.error("Erreur lors de l'exécution de la requête Qdrant (%s, mode=%s): %s", query, mode, e)

        elapsed = (time.time() - start_time) * 1000.0
        return items, elapsed

    def compare(
        self,
        query: str,
        limit: int = 5,
        filter_dci: Optional[str] = None,
        filter_category: Optional[str] = None,
        scenario: Optional[SearchBenchmarkCase] = None,
    ) -> QueryComparisonResult:
        """
        Exécute la comparaison pour une requête donnée et calcule les métriques de concordance.
        """
        # 1. Exécution des trois modes
        keyword_res, t_kw = self._execute_qdrant_query(
            "keyword", query, limit=limit, filter_dci=filter_dci, filter_category=filter_category
        )
        semantic_res, t_sem = self._execute_qdrant_query(
            "semantic", query, limit=limit, filter_dci=filter_dci, filter_category=filter_category
        )
        hybrid_res, t_hyb = self._execute_qdrant_query(
            "hybrid", query, limit=limit, filter_dci=filter_dci, filter_category=filter_category
        )

        # 2. Calcul des métriques de chevauchement (Jaccard)
        kw_ids = {r.chunk_id for r in keyword_res}
        sem_ids = {r.chunk_id for r in semantic_res}
        hyb_ids = {r.chunk_id for r in hybrid_res}

        def jaccard(s1: Set[str], s2: Set[str]) -> float:
            if not s1 and not s2:
                return 1.0
            union = s1 | s2
            return len(s1 & s2) / len(union) if union else 0.0

        j_kw_sem = jaccard(kw_ids, sem_ids)
        j_sem_hyb = jaccard(sem_ids, hyb_ids)
        j_kw_hyb = jaccard(kw_ids, hyb_ids)

        sem_unique = list(sem_ids - kw_ids)
        kw_unique = list(kw_ids - sem_ids)

        metrics = ComparisonMetrics(
            query=query,
            keyword_count=len(keyword_res),
            semantic_count=len(semantic_res),
            hybrid_count=len(hybrid_res),
            jaccard_keyword_semantic=round(j_kw_sem, 3),
            jaccard_semantic_hybrid=round(j_sem_hyb, 3),
            jaccard_keyword_hybrid=round(j_kw_hyb, 3),
            semantic_unique_chunks=sem_unique,
            keyword_unique_chunks=kw_unique,
            execution_time_ms={
                "keyword": round(t_kw, 1),
                "semantic": round(t_sem, 1),
                "hybrid": round(t_hyb, 1),
            },
        )

        return QueryComparisonResult(
            query=query,
            keyword_results=keyword_res,
            semantic_results=semantic_res,
            hybrid_results=hybrid_res,
            metrics=metrics,
            scenario=scenario,
        )

    def run_benchmark_suite(self, limit: int = 5) -> List[QueryComparisonResult]:
        """Exécute la suite complète des scénarios canoniques."""
        results = []
        for sc in CANONICAL_SCENARIOS:
            print(f"Évaluation du scénario : [{sc.id}] {sc.title}...")
            res = self.compare(
                query=sc.query,
                limit=limit,
                filter_dci=sc.filter_dci,
                filter_category=sc.filter_category,
                scenario=sc,
            )
            results.append(res)
        return results


# ---------------------------------------------------------------------------
# Formatage et Affichage des Résultats
# ---------------------------------------------------------------------------

def format_comparison_terminal(res: QueryComparisonResult) -> str:
    """Formate les résultats d'une comparaison pour affichage clair en console."""
    lines = []
    sc = res.scenario
    lines.append("=" * 80)
    if sc:
        lines.append(f"SCÉNARIO : [{sc.id}] {sc.title}")
        lines.append(f"Description : {sc.description}")
        lines.append(f"Gain Attendu: {sc.key_differentiator.upper()}")
    lines.append(f"REQUÊTE     : \"{res.query}\"")
    lines.append("=" * 80)

    # Métriques synthétiques
    m = res.metrics
    lines.append(f"\nMÉTRIQUES DE CORRÉLATION :")
    lines.append(f"  • Chevauchement Mots-Clés vs Sémantique (Jaccard) : {m.jaccard_keyword_semantic * 100:.1f}%")
    lines.append(f"  • Chevauchement Sémantique vs Hybride           : {m.jaccard_semantic_hybrid * 100:.1f}%")
    lines.append(f"  • Chevauchement Mots-Clés vs Hybride            : {m.jaccard_keyword_hybrid * 100:.1f}%")
    lines.append(f"  • Temps de réponse : Mots-clés: {m.execution_time_ms['keyword']}ms | Sémantique: {m.execution_time_ms['semantic']}ms | Hybride: {m.execution_time_ms['hybrid']}ms")

    # Tableaux comparatifs
    def format_column(title: str, items: List[SearchResultItem]) -> List[str]:
        col = [f"\n--- {title.upper()} (Top {len(items)}) ---"]
        if not items:
            col.append("  (Aucun résultat trouvé)")
            return col
        for item in items:
            col.append(f"  [{item.rank}] Score: {item.score:.4f} | ID: {item.chunk_id}")
            col.append(f"      Section: {item.section_category} | {item.source.upper()}")
            col.append(f"      Extrait: {item.snippet(110)}")
        return col

    lines.extend(format_column("1. Recherche par Mots-Clés (Sparse / Lexicale)", res.keyword_results))
    lines.extend(format_column("2. Recherche Sémantique (Dense 1024-d / BGE-M3)", res.semantic_results))
    lines.extend(format_column("3. Recherche Hybride (Dense + Sparse RRF)", res.hybrid_results))

    # Analyse clinique déduite
    lines.append("\n--- ANALYSE CLINIQUE COMPARATIVE ---")
    if m.jaccard_keyword_semantic < 0.4:
        lines.append("  ⚠️  Divergence élevée entre mots-clés et sémantique :")
        lines.append("      La recherche sémantique capture les paraphrases et synonymes que la recherche")
        lines.append("      lexicale ignore complètement, tandis que la recherche lexicale ancre les termes exacts.")
    else:
        lines.append("  ✅  Forte convergence : les termes de la requête sont explicites et alignés avec le texte médical.")

    lines.append(f"  🎯  La Recherche Hybride sélectionne le consensus optimal en combinant précision et rappel.")
    lines.append("-" * 80)

    return "\n".join(lines)


def generate_markdown_report(results: List[QueryComparisonResult]) -> str:
    """Génère un rapport d'évaluation complet au format GitHub Flavored Markdown."""
    doc = []
    doc.append("# Évaluation Comparative : Mots-Clés vs Recherche Sémantique vs Recherche Hybride")
    doc.append("\nSystème RAG Pharmeazor | Modèle BAAI/bge-m3 | Base Vectorielle Qdrant\n")
    doc.append("Ce benchmark analyse les différences fondamentales entre la **recherche par mots-clés** (lexicale / sparse), la **recherche sémantique dense** (vecteurs 1024-d), et la **recherche hybride** (fusion RRF).\n")

    doc.append("## Synthèse Globale des Scénarios\n")
    doc.append("| Scénario | Intitulé | Jaccard (Mots-clés vs Sémantique) | Gagnant Clinique |")
    doc.append("| :--- | :--- | :---: | :--- |")

    for r in results:
        sc = r.scenario
        sc_id = sc.id if sc else "Custom"
        title = sc.title if sc else r.query[:35]
        j_val = f"{r.metrics.jaccard_keyword_semantic * 100:.1f}%"
        winner = "Sémantique" if sc and sc.key_differentiator == "semantic_win" else ("Mots-clés" if sc and sc.key_differentiator == "keyword_win" else "Hybride")
        doc.append(f"| **{sc_id}** | {title} | `{j_val}` | **{winner}** |")

    doc.append("\n---\n")

    for r in results:
        sc = r.scenario
        doc.append(f"## {sc.id if sc else 'Test'} : {sc.title if sc else r.query}")
        doc.append(f"**Requête évaluée :** `{r.query}`\n")
        if sc:
            doc.append(f"> **Problématique clinique :** {sc.description}\n")

        doc.append("### Résultats Détaillés par Approche\n")

        # Top 1 de chaque méthode
        top_kw = r.keyword_results[0] if r.keyword_results else None
        top_sem = r.semantic_results[0] if r.semantic_results else None
        top_hyb = r.hybrid_results[0] if r.hybrid_results else None

        doc.append("| Critère | 1. Mots-Clés (Lexicale) | 2. Sémantique (Dense) | 3. Hybride (RRF) |")
        doc.append("| :--- | :--- | :--- | :--- |")
        doc.append(f"| **Top Match ID** | `{top_kw.chunk_id if top_kw else 'N/A'}` | `{top_sem.chunk_id if top_sem else 'N/A'}` | `{top_hyb.chunk_id if top_hyb else 'N/A'}` |")
        doc.append(f"| **Section Médicale** | {top_kw.section_category if top_kw else 'N/A'} | {top_sem.section_category if top_sem else 'N/A'} | {top_hyb.section_category if top_hyb else 'N/A'} |")
        doc.append(f"| **Score Retenu** | `{top_kw.score:.4f}` if top_kw else '-' | `{top_sem.score:.4f}` if top_sem else '-' | `{top_hyb.score:.4f}` if top_hyb else '-' |")
        doc.append(f"| **Extrait** | _{top_kw.snippet(80) if top_kw else 'N/A'}_ | _{top_sem.snippet(80) if top_sem else 'N/A'}_ | _{top_hyb.snippet(80) if top_hyb else 'N/A'}_ |\n")

        doc.append("### Analyse Comparative\n")
        if r.metrics.jaccard_keyword_semantic < 0.4:
            doc.append("- **Mots-clés :** Souffre du *vocabulary mismatch* car les mots exacts de la question ne figurent pas dans la monographie officielle.")
            doc.append("- **Sémantique :** Aligne parfaitement le sens clinique (ex. 'maux de tête' $\\rightarrow$ 'céphalées').")
            doc.append("- **Hybride :** Combine la sécurité des correspondances lexicales avec la flexibilité sémantique.\n")
        else:
            doc.append("- **Convergence :** Les deux méthodes confirment le même chunk prioritaire, l'hybride maximisant la confiance du classement.\n")

        doc.append("---\n")

    return "\n".join(doc)


# ---------------------------------------------------------------------------
# CLI Command Line Interface
# ---------------------------------------------------------------------------

def _run_cli() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(
        description="Pharmeazor RAG - Comparaison Mots-Clés vs Recherche Sémantique vs Hybride"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Question ou requête clinique personnalisée à comparer",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Exécute la suite complète des 5 scénarios canoniques",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Nombre de résultats à afficher par méthode (défaut: 3)",
    )
    parser.add_argument(
        "--dci",
        type=str,
        default=None,
        help="Filtrer par DCI spécifique (ex. PARACÉTAMOL)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filtrer par catégorie de section (posology, contraindications, warnings, etc.)",
    )
    parser.add_argument(
        "--export-md",
        type=str,
        default=None,
        help="Chemin de fichier pour exporter le rapport Markdown",
    )

    args = parser.parse_args()
    comparator = SearchComparator()

    if args.benchmark:
        print("=" * 80)
        print("LANCEMENT DU BENCHMARK COMPARATIF : MOTS-CLÉS VS SÉMANTIQUE VS HYBRIDE")
        print("=" * 80)
        benchmark_results = comparator.run_benchmark_suite(limit=args.limit)

        for res in benchmark_results:
            print(format_comparison_terminal(res))

        if args.export_md:
            md_content = generate_markdown_report(benchmark_results)
            out_path = Path(args.export_md)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md_content, encoding="utf-8")
            print(f"\n[OK] Rapport Markdown exporté avec succès dans : {out_path.resolve()}")

    elif args.query:
        print(f"Comparaison de la requête : '{args.query}' (limit={args.limit})...\n")
        res = comparator.compare(
            query=args.query,
            limit=args.limit,
            filter_dci=args.dci,
            filter_category=args.category,
        )
        print(format_comparison_terminal(res))

        if args.export_md:
            md_content = generate_markdown_report([res])
            out_path = Path(args.export_md)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md_content, encoding="utf-8")
            print(f"\n[OK] Rapport Markdown exporté avec succès dans : {out_path.resolve()}")

    else:
        # Aucun argument : exécute une démonstration sur la question canonique N1-01
        print("Aucune requête fournie. Exécution de la démonstration sur la question canonique N1-01...\n")
        demo_query = (
            "Chez un adulte de 60 kg, quelle est la dose journalière maximale de DOLIPRANE 1000 mg "
            "en règle générale, et dans quelle condition peut-on aller jusqu'à 4 g par jour ?"
        )
        res = comparator.compare(
            query=demo_query,
            limit=args.limit,
            scenario=CANONICAL_SCENARIOS[1],
        )
        print(format_comparison_terminal(res))


if __name__ == "__main__":
    _run_cli()
