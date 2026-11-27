"""
Pharmeazor Knowledge Graph - Neo4j Graph Storage Module
=======================================================
Provides a robust, transaction-safe persistence layer for storing, querying,
and managing pharmaceutical Knowledge Graph entities and relationships in Neo4j.

Reuses official ontology models from:
- ai_api.Augmentation.knowledge_graph.ontology (KGEntity, KGRelation, EntityType, RelationType)
- ai_api.Augmentation.knowledge_graph.relationship_extractor (ExtractionResult)
- ai_api.Augmentation.knowledge_graph.provenance (ProvenanceRecord)

Strict Medical Safety & Data Integrity:
- Preserves verbatim clinical evidence and provenance without modification.
- Never creates orphaned relationships without verifying source and target existence.
- Idempotent operations via Cypher MERGE to prevent duplicate nodes and edges.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Augmentation.knowledge_graph.ontology import (
    EntityType,
    InteractionSeverity,
    KGEntity,
    KGRelation,
    RelationType,
    SourceAuthority,
)

logger = logging.getLogger(__name__)

# Graceful import of official Neo4j driver
try:
    import neo4j
    from neo4j import Driver, GraphDatabase, Session, Transaction
    from neo4j.exceptions import ClientError, DatabaseError, Neo4jError, ServiceUnavailable
    NEO4J_AVAILABLE = True
except ImportError:
    neo4j = None  # type: ignore
    GraphDatabase = None  # type: ignore
    Driver = Any  # type: ignore
    Session = Any  # type: ignore
    Transaction = Any  # type: ignore
    Neo4jError = Exception  # type: ignore
    ServiceUnavailable = Exception  # type: ignore
    ClientError = Exception  # type: ignore
    DatabaseError = Exception  # type: ignore
    NEO4J_AVAILABLE = False


# ==============================================================================
# EXCEPTIONS
# ==============================================================================

class GraphStorageError(Exception):
    """Base exception for graph storage operations."""
    pass


class StorageConnectionError(GraphStorageError):
    """Raised when connecting or authenticating with Neo4j fails."""
    pass


class MissingEntityError(GraphStorageError):
    """Raised when attempting to create a relationship between non-existent entities."""
    pass


class ConstraintError(GraphStorageError):
    """Raised when constraint initialization fails."""
    pass


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class Neo4jConfig:
    """Connection and operational configuration for Neo4j database."""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connection_lifetime_sec: int = 3600
    max_connection_pool_size: int = 50
    connection_timeout_sec: float = 30.0

    @classmethod
    def from_env(cls) -> Neo4jConfig:
        """Loads configuration from standard environment variables."""
        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            max_connection_lifetime_sec=int(os.getenv("NEO4J_MAX_CONNECTION_LIFETIME", "3600")),
            max_connection_pool_size=int(os.getenv("NEO4J_MAX_POOL_SIZE", "50")),
            connection_timeout_sec=float(os.getenv("NEO4J_CONNECTION_TIMEOUT", "30.0")),
        )


def _json_default(value: Any) -> Any:
    """Serialize common ontology values nested inside metadata dictionaries."""
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (set, tuple)):
        return list(value)
    if isinstance(value, Path):
        return value.as_posix()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return str(value)


def _enum_value(value: Any, enum_type: Any, field_name: str) -> Any:
    """Normalize enum instances or serialized enum values before storage."""
    if value is None:
        return None
    if isinstance(value, enum_type):
        return value.value
    try:
        return enum_type(value).value
    except (TypeError, ValueError):
        if isinstance(value, str):
            try:
                return enum_type[value].value
            except KeyError:
                try:
                    return enum_type(int(value)).value
                except (TypeError, ValueError):
                    pass
        raise ValueError(f"Invalid {field_name}: {value}")


# ==============================================================================
# PROPERTY SANITIZATION FOR NEO4J
# ==============================================================================

def sanitize_neo4j_properties(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts Python data types into Neo4j-compatible property types:
    - Primitives (str, int, float, bool) are preserved.
    - Homogeneous lists of primitives are preserved.
    - Nested dictionaries and complex objects are serialized to JSON strings.
    - None values are excluded.
    """
    sanitized: Dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, (list, tuple, set)):
            # Check if all items in list are strings or numbers
            val_list = list(value)
            if not val_list:
                sanitized[key] = []
            elif all(isinstance(x, (str, int, float, bool)) for x in val_list):
                # Ensure homogeneous string list if mixed
                if all(isinstance(x, str) for x in val_list):
                    sanitized[key] = val_list
                else:
                    sanitized[key] = [str(x) for x in val_list]
            else:
                sanitized[key] = json.dumps(val_list, ensure_ascii=False, default=_json_default)
        elif isinstance(value, dict):
            sanitized[key] = json.dumps(value, ensure_ascii=False, default=_json_default)
        else:
            sanitized[key] = str(value)
    return sanitized


def _unique_values(*values: Any) -> List[Any]:
    """Flatten optional scalar/list values while preserving first-seen order."""
    unique: List[Any] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, set):
            items = sorted(value, key=str)
        else:
            items = value if isinstance(value, (list, tuple)) else [value]
        for item in items:
            if item is None or item == "" or item in unique:
                continue
            unique.append(item)
    return unique


def _unique_string_values(*values: Any) -> List[str]:
    """Return unique non-empty string values for Neo4j list properties."""
    return [str(value) for value in _unique_values(*values) if str(value)]


# ==============================================================================
# MAIN GRAPH STORAGE CLASS
# ==============================================================================

class GraphStorage:
    """
    Neo4j Graph Database Storage Manager for Pharmeazor.
    Manages connections, schema constraints, entity nodes, and clinical edges.
    """

    def __init__(
        self,
        config: Optional[Neo4jConfig] = None,
        driver: Optional[Any] = None,
    ):
        self.config = config or Neo4jConfig.from_env()
        self._driver = driver
        self._owns_driver = driver is None

    # --------------------------------------------------------------------------
    # Driver & Connection Management
    # --------------------------------------------------------------------------

    @property
    def driver(self) -> Driver:
        """Returns the active driver or initializes a new connection."""
        if self._driver is None:
            self._connect()
        return self._driver

    def _connect(self) -> None:
        """Initializes the Neo4j driver with configured credentials and pool settings."""
        if not NEO4J_AVAILABLE:
            raise StorageConnectionError(
                "The 'neo4j' official Python driver is not installed. "
                "Install the project dependencies with: python -m pip install -r ai_api/requirements.txt"
            )
        if self.config.username and not self.config.password:
            raise StorageConnectionError(
                "NEO4J_PASSWORD is empty. Set the Neo4j password in ai_api/.env "
                "or provide it through the environment."
            )

        try:
            auth = (self.config.username, self.config.password) if self.config.username else None
            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=auth,
                max_connection_lifetime=self.config.max_connection_lifetime_sec,
                max_connection_pool_size=self.config.max_connection_pool_size,
                connection_timeout=self.config.connection_timeout_sec,
            )
            logger.info("Initialized Neo4j driver for URI: %s (database: %s)", self.config.uri, self.config.database)
        except Exception as exc:
            logger.error("Failed to initialize Neo4j driver: %s", exc)
            raise StorageConnectionError(f"Failed to connect to Neo4j at {self.config.uri}: {exc}") from exc

    def verify_connectivity(self) -> bool:
        """
        Actively checks whether the Neo4j database is reachable and authenticated.
        Returns True on success, raises StorageConnectionError on failure.
        """
        try:
            self.driver.verify_connectivity()
            logger.info("Neo4j connectivity verified successfully.")
            return True
        except Exception as exc:
            logger.error("Neo4j connectivity check failed: %s", exc)
            raise StorageConnectionError(f"Neo4j is unreachable at {self.config.uri}: {exc}") from exc

    def get_session(self) -> Session:
        """Opens and returns a new session for the configured database."""
        return self.driver.session(database=self.config.database)

    def close(self) -> None:
        """Closes the Neo4j driver connection pool."""
        if self._driver and self._owns_driver:
            self._driver.close()
            self._driver = None
            logger.info("Closed Neo4j driver connection pool.")

    def __enter__(self) -> GraphStorage:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # --------------------------------------------------------------------------
    # Constraints and Indexes Initialization
    # --------------------------------------------------------------------------

    def create_constraints(self) -> None:
        """
        Creates idempotent uniqueness constraints and indexes for entities and types.
        Safe to call multiple times.
        """
        statements = [
            # 1. Global uniqueness constraint on Entity ID
            """
            CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
            FOR (e:Entity)
            REQUIRE e.id IS UNIQUE
            """,
            # 2. General name index for fast lexical retrieval
            """
            CREATE INDEX entity_name_idx IF NOT EXISTS
            FOR (e:Entity)
            ON (e.name)
            """,
            # 3. Entity type index for filtering
            """
            CREATE INDEX entity_type_idx IF NOT EXISTS
            FOR (e:Entity)
            ON (e.entity_type)
            """,
            # 4. Drug ID metadata index for linking to source datasets
            """
            CREATE INDEX drug_id_idx IF NOT EXISTS
            FOR (e:Entity)
            ON (e.drug_id)
            """,
        ]

        # Add per-entity-type uniqueness constraints
        for etype in EntityType:
            statements.append(
                f"""
                CREATE INDEX {etype.value.lower()}_id_idx IF NOT EXISTS
                FOR (e:{etype.value})
                ON (e.id)
                """
            )

        failures: List[str] = []
        with self.get_session() as session:
            for query in statements:
                try:
                    session.run(query).consume()
                except Exception as exc:
                    logger.warning("Constraint or index statement warning: %s (%s)", exc, query.strip())
                    failures.append(str(exc))

        if failures:
            raise ConstraintError(
                f"Failed to create or verify {len(failures)} Neo4j constraint/index statement(s): "
                + "; ".join(failures[:3])
            )

        logger.info("Neo4j schema constraints and indexes verified.")

    # --------------------------------------------------------------------------
    # Single Entity Storage
    # --------------------------------------------------------------------------

    def store_entity(
        self,
        entity: KGEntity,
        session_or_tx: Optional[Union[Session, Transaction]] = None,
    ) -> Dict[str, Any]:
        """
        Stores or updates an entity node in Neo4j.
        Labels the node with :Entity and :{entity_type.value}.
        Preserves existing data and avoids overwriting with null.
        """
        # Validate EntityType against ontology enum to avoid Cypher injection
        if not isinstance(entity.entity_type, EntityType):
            try:
                valid_type = EntityType(str(entity.entity_type))
            except ValueError:
                raise ValueError(f"Invalid EntityType: {entity.entity_type}")
        else:
            valid_type = entity.entity_type

        label = valid_type.value

        # Prepare parameters
        aliases = list(dict.fromkeys(entity.aliases + [entity.name]))  # remove duplicates

        # Flatten metadata primitives
        props = sanitize_neo4j_properties(entity.metadata)
        props["id"] = entity.id
        props["name"] = entity.name
        props["entity_type"] = valid_type.value
        props["aliases"] = aliases
        props["metadata_json"] = json.dumps(entity.metadata, ensure_ascii=False, default=_json_default)
        if entity.collection_date:
            props["collection_date"] = entity.collection_date

        cypher = f"""
        MERGE (e:Entity {{id: $id}})
        SET e:{label},
            e.name = $name,
            e.entity_type = $entity_type,
            e.aliases = $aliases,
            e.metadata_json = $metadata_json,
            e += $props,
            e.updated_at = timestamp()
        RETURN e.id AS id, e.name AS name, labels(e) AS labels
        """

        def _execute(tx: Transaction) -> Dict[str, Any]:
            result = tx.run(cypher, id=entity.id, name=entity.name, entity_type=valid_type.value, aliases=aliases, metadata_json=props["metadata_json"], props=props)
            record = result.single()
            return dict(record) if record else {"id": entity.id}

        if session_or_tx is not None:
            if hasattr(session_or_tx, "run"):  # Transaction or Session
                return _execute(session_or_tx)  # type: ignore

        with self.get_session() as session:
            return session.execute_write(_execute)

    # --------------------------------------------------------------------------
    # Single Relationship Storage
    # --------------------------------------------------------------------------

    def store_relation(
        self,
        relation: KGRelation,
        session_or_tx: Optional[Union[Session, Transaction]] = None,
    ) -> Dict[str, Any]:
        """
        Stores a directed clinical or structural relationship between two entities.
        Strictly requires that source and target nodes exist. Raises MissingEntityError otherwise.
        """
        # Validate RelationType against ontology enum
        if not isinstance(relation.relation_type, RelationType):
            try:
                valid_rel_type = RelationType(str(relation.relation_type))
            except ValueError:
                raise ValueError(f"Invalid RelationType: {relation.relation_type}")
        else:
            valid_rel_type = relation.relation_type

        rel_label = valid_rel_type.value

        def _execute(tx: Transaction) -> Dict[str, Any]:
            # 1. Verify existence of source and target entities
            check_cypher = """
            OPTIONAL MATCH (s:Entity {id: $source_id})
            WITH count(s) > 0 AS source_exists
            OPTIONAL MATCH (t:Entity {id: $target_id})
            RETURN source_exists, count(t) > 0 AS target_exists
            """
            check_res = tx.run(check_cypher, source_id=relation.source_id, target_id=relation.target_id).single()
            source_exists = bool(check_res and check_res["source_exists"])
            target_exists = bool(check_res and check_res["target_exists"])

            if not source_exists and not target_exists:
                raise MissingEntityError(
                    f"Cannot create relation '{rel_label}': Neither source '{relation.source_id}' "
                    f"nor target '{relation.target_id}' exist in Neo4j."
                )
            if not source_exists:
                raise MissingEntityError(
                    f"Cannot create relation '{rel_label}': Source entity '{relation.source_id}' "
                    f"does not exist in Neo4j."
                )
            if not target_exists:
                raise MissingEntityError(
                    f"Cannot create relation '{rel_label}': Target entity '{relation.target_id}' "
                    f"does not exist in Neo4j."
                )

            # 2. Prepare relationship properties and preserve repeated provenance.
            metadata = relation.metadata or {}
            source_docs = _unique_string_values(
                relation.source_doc,
                metadata.get("source_doc"),
                metadata.get("source_docs"),
            )
            source_chunk_ids = _unique_string_values(
                relation.source_chunk_id,
                metadata.get("source_chunk_id"),
                metadata.get("source_chunk_ids"),
            )
            source_urls = _unique_string_values(metadata.get("source_url"), metadata.get("source_urls"))
            source_authority = _enum_value(
                relation.source_authority, SourceAuthority, "SourceAuthority"
            )
            collection_date = relation.collection_date
            severity = _enum_value(relation.severity, InteractionSeverity, "InteractionSeverity")
            evidence_text = str(metadata.get("evidence_text") or relation.description)
            metadata_json = json.dumps(metadata, ensure_ascii=False, default=_json_default)

            rel_props = sanitize_neo4j_properties(metadata)
            # These fields are managed explicitly below so flattened metadata
            # cannot overwrite the ontology fields or accumulated provenance.
            for reserved in (
                "description", "confidence", "source_doc", "source_docs", "source_chunk_id", "source_chunk_ids",
                "source_url", "source_urls", "source_authority", "source_authorities",
                "collection_date", "collection_dates", "severity", "severities",
                "evidence_text", "evidence_texts", "metadata_json", "metadata_jsons",
            ):
                rel_props.pop(reserved, None)
            rel_props["description"] = relation.description
            rel_props["confidence"] = float(relation.confidence)
            rel_props["evidence_text"] = evidence_text
            rel_props["metadata_json"] = metadata_json
            if source_docs:
                rel_props["source_doc"] = source_docs[-1]
            if source_chunk_ids:
                rel_props["source_chunk_id"] = source_chunk_ids[-1]
            if source_urls:
                rel_props["source_url"] = source_urls[-1]
            if metadata.get("section_key") is not None:
                rel_props["section_key"] = str(metadata["section_key"])
            if metadata.get("section_number") is not None:
                rel_props["section_number"] = str(metadata["section_number"])

            metadata_jsons = [metadata_json] if metadata_json else []
            source_authorities = [source_authority] if source_authority is not None else []
            collection_dates = [collection_date] if collection_date else []
            severities = [severity] if severity else []
            evidence_texts = [evidence_text] if evidence_text else []

            # 3. Create or Merge Relationship
            cypher = f"""
            MATCH (source:Entity {{id: $source_id}})
            MATCH (target:Entity {{id: $target_id}})
            MERGE (source)-[r:{rel_label}]->(target)
            SET r += $props,
                r.description = CASE
                    WHEN size($description) > size(coalesce(r.description, '')) THEN $description
                    ELSE coalesce(r.description, $description)
                END,
                r.confidence = CASE
                    WHEN r.confidence IS NULL OR $confidence > r.confidence THEN $confidence
                    ELSE r.confidence
                END,
                r.source_docs = reduce(acc = coalesce(r.source_docs, []), item IN $source_docs |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END),
                r.source_chunk_ids = reduce(acc = coalesce(r.source_chunk_ids, []), item IN $source_chunk_ids |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END),
                r.source_urls = reduce(acc = coalesce(r.source_urls, []), item IN $source_urls |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END),
                r.source_authorities = reduce(acc = coalesce(r.source_authorities, []), item IN $source_authorities |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END),
                r.collection_dates = reduce(acc = coalesce(r.collection_dates, []), item IN $collection_dates |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END),
                r.severities = reduce(acc = coalesce(r.severities, []), item IN $severities |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END),
                r.evidence_texts = reduce(acc = coalesce(r.evidence_texts, []), item IN $evidence_texts |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END),
                r.metadata_jsons = reduce(acc = coalesce(r.metadata_jsons, []), item IN $metadata_jsons |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END),
                r.source_authority = CASE
                    WHEN $source_authority IS NULL THEN r.source_authority
                    WHEN r.source_authority IS NULL THEN $source_authority
                    WHEN toInteger(r.source_authority) IS NULL THEN $source_authority
                    WHEN $source_authority < toInteger(r.source_authority) THEN $source_authority
                    ELSE toInteger(r.source_authority)
                END,
                r.collection_date = CASE
                    WHEN $collection_date IS NULL THEN r.collection_date
                    ELSE $collection_date
                END,
                r.severity = CASE WHEN $severity IS NULL THEN r.severity ELSE $severity END,
                r.updated_at = timestamp()
            RETURN type(r) AS rel_type, source.id AS source_id, target.id AS target_id
            """
            res = tx.run(
                cypher,
                source_id=relation.source_id,
                target_id=relation.target_id,
                props=rel_props,
                description=relation.description,
                confidence=float(relation.confidence),
                source_docs=source_docs,
                source_chunk_ids=source_chunk_ids,
                source_urls=source_urls,
                source_authorities=source_authorities,
                collection_dates=collection_dates,
                severities=severities,
                evidence_texts=evidence_texts,
                metadata_jsons=metadata_jsons,
                source_authority=source_authority,
                collection_date=collection_date,
                severity=severity,
            )
            rec = res.single()
            return dict(rec) if rec else {"source_id": relation.source_id, "target_id": relation.target_id}

        if session_or_tx is not None:
            if hasattr(session_or_tx, "run"):
                return _execute(session_or_tx)  # type: ignore

        with self.get_session() as session:
            return session.execute_write(_execute)

    # --------------------------------------------------------------------------
    # Complete Graph Storage (Batch & Atomic)
    # --------------------------------------------------------------------------

    def store_graph(
        self,
        graph_data: Any,
    ) -> Dict[str, Any]:
        """
        Stores a complete graph structure (entities + relationships) atomically.
        Accepts:
        - ExtractionResult (from relationship_extractor)
        - Dict with keys 'entities' and 'relations' (or 'relationships')
        - Tuple of (List[KGEntity], List[KGRelation])

        All entities are stored first, followed by all relationships.
        Rolls back the entire transaction if any critical operation fails.
        """
        # Parse inputs
        entities: List[KGEntity] = []
        relations: List[KGRelation] = []

        if hasattr(graph_data, "entities") and hasattr(graph_data, "relations"):
            entities = list(graph_data.entities)
            relations = list(graph_data.relations)
        elif isinstance(graph_data, dict):
            raw_ents = graph_data.get("entities", [])
            raw_rels = graph_data.get("relations") or graph_data.get("relationships", [])

            entities = [e if isinstance(e, KGEntity) else KGEntity.from_dict(e) for e in raw_ents]
            relations = [r if isinstance(r, KGRelation) else KGRelation.from_dict(r) for r in raw_rels]
        elif isinstance(graph_data, (tuple, list)) and len(graph_data) == 2:
            entities = list(graph_data[0])
            relations = list(graph_data[1])
        else:
            raise ValueError(
                f"Unsupported graph_data format: {type(graph_data)}. "
                "Expected ExtractionResult, dict with 'entities'/'relations', or (entities, relations) tuple."
            )

        def _atomic_write_tx(tx: Transaction) -> Dict[str, Any]:
            # Neo4j may retry this callback after a transient failure. Keep
            # counters local so retries cannot inflate the returned summary.
            nodes_stored = 0
            rels_stored = 0
            failed_relations: List[Dict[str, str]] = []

            # Step 1: Store all entities first
            for ent in entities:
                self.store_entity(ent, session_or_tx=tx)
                nodes_stored += 1

            # Step 2: Store all relationships
            for rel in relations:
                try:
                    self.store_relation(rel, session_or_tx=tx)
                    rels_stored += 1
                except MissingEntityError as err:
                    logger.warning("Skipping orphaned relation in batch: %s", err)
                    failed_relations.append({
                        "edge_key": rel.edge_key,
                        "reason": str(err),
                    })

            return {
                "nodes_stored": nodes_stored,
                "relationships_stored": rels_stored,
                "relationships_skipped": len(failed_relations),
                "skipped_details": failed_relations,
            }

        with self.get_session() as session:
            summary = session.execute_write(_atomic_write_tx)

        logger.info(
            "Graph storage completed: %d nodes, %d relationships stored (%d skipped).",
            summary["nodes_stored"],
            summary["relationships_stored"],
            summary["relationships_skipped"],
        )
        return summary

    # --------------------------------------------------------------------------
    # Query & Utility Methods
    # --------------------------------------------------------------------------

    def get_entity_by_id(self, entity_id: str) -> Optional[KGEntity]:
        """Retrieves and reconstructs a KGEntity by its unique canonical ID."""
        cypher = """
        MATCH (e:Entity {id: $id})
        RETURN e.id AS id,
               e.name AS name,
               e.entity_type AS entity_type,
               e.aliases AS aliases,
               e.collection_date AS collection_date,
               e.metadata_json AS metadata_json,
               properties(e) AS props
        """
        with self.get_session() as session:
            rec = session.run(cypher, id=entity_id).single()
            if not rec:
                return None

            raw_meta_json = rec.get("metadata_json")
            metadata: Dict[str, Any] = {}
            if raw_meta_json:
                try:
                    metadata = json.loads(raw_meta_json)
                except Exception:
                    metadata = {}

            # Reconstruct EntityType enum safely
            raw_type = rec["entity_type"]
            try:
                etype = EntityType(raw_type)
            except ValueError:
                etype = EntityType.DRUG

            return KGEntity(
                id=rec["id"],
                name=rec["name"],
                entity_type=etype,
                aliases=rec.get("aliases") or [],
                collection_date=rec.get("collection_date"),
                metadata=metadata,
            )

    def entity_exists(self, entity_id: str) -> bool:
        """Checks if an entity node exists in Neo4j."""
        cypher = "MATCH (e:Entity {id: $id}) RETURN count(e) AS count"
        with self.get_session() as session:
            rec = session.run(cypher, id=entity_id).single()
            return bool(rec and rec["count"] > 0)

    def delete_entity(self, entity_id: str, detach: bool = True) -> bool:
        """Deletes an entity node and optionally detaches its relationships."""
        detach_clause = "DETACH DELETE e" if detach else "DELETE e"
        cypher = f"""
        MATCH (e:Entity {{id: $id}})
        {detach_clause}
        RETURN count(e) AS deleted_count
        """
        with self.get_session() as session:
            rec = session.run(cypher, id=entity_id).single()
            return bool(rec and rec["deleted_count"] > 0)

    def clear_database(self, confirm: bool = False) -> int:
        """
        SAFETY-PROTECTED: Deletes all nodes and relationships in the database.
        Requires explicit confirm=True.
        """
        if not confirm:
            raise ValueError(
                "SAFETY RESTRICTION: clear_database() requires explicit confirm=True. "
                "This action permanently deletes all graph data."
            )

        cypher = """
        MATCH (n)
        DETACH DELETE n
        RETURN count(n) AS deleted_nodes
        """
        with self.get_session() as session:
            res = session.run(cypher).single()
            count = res["deleted_nodes"] if res else 0
            logger.warning("Database CLEARED: deleted %d nodes.", count)
            return count

    def get_graph_statistics(self) -> Dict[str, Any]:
        """Calculates total counts and type breakdowns of all nodes and relationships in Neo4j."""
        node_counts_cypher = """
        MATCH (e:Entity)
        RETURN e.entity_type AS entity_type, count(e) AS count
        """
        rel_counts_cypher = """
        MATCH ()-[r]->()
        RETURN type(r) AS relation_type, count(r) AS count
        """
        total_cypher = """
        MATCH (n)
        OPTIONAL MATCH ()-[r]->()
        RETURN count(DISTINCT n) AS total_nodes, count(DISTINCT r) AS total_relationships
        """

        stats: Dict[str, Any] = {
            "total_nodes": 0,
            "total_relationships": 0,
            "entity_breakdown": {},
            "relationship_breakdown": {},
        }

        with self.get_session() as session:
            tot = session.run(total_cypher).single()
            if tot:
                stats["total_nodes"] = tot["total_nodes"]
                stats["total_relationships"] = tot["total_relationships"]

            for rec in session.run(node_counts_cypher):
                k = rec["entity_type"] or "UNKNOWN"
                stats["entity_breakdown"][k] = rec["count"]

            for rec in session.run(rel_counts_cypher):
                k = rec["relation_type"] or "UNKNOWN"
                stats["relationship_breakdown"][k] = rec["count"]

        return stats

    def get_neighbors(
        self,
        entity_id: str,
        relation_types: Optional[List[RelationType]] = None,
        direction: str = "both",
    ) -> List[Dict[str, Any]]:
        """
        Retrieves directly connected neighbor entities and clinical relationships.
        Useful for GraphRAG context injection.
        """
        rel_filter = ""
        if relation_types:
            type_names = []
            for relation_type in relation_types:
                try:
                    normalized_type = (
                        relation_type
                        if isinstance(relation_type, RelationType)
                        else RelationType(str(relation_type))
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid relation type: {relation_type}") from exc
                if normalized_type.value not in type_names:
                    type_names.append(normalized_type.value)
            rel_filter = ":" + "|:".join(type_names)

        if direction not in {"in", "out", "both"}:
            raise ValueError("direction must be 'in', 'out', or 'both'")

        if direction == "out":
            pattern = f"(e)-[r{rel_filter}]->(neighbor:Entity)"
        elif direction == "in":
            pattern = f"(e)<-[r{rel_filter}]-(neighbor:Entity)"
        else:
            pattern = f"(e)-[r{rel_filter}]-(neighbor:Entity)"

        cypher = f"""
        MATCH (e:Entity {{id: $id}})
        MATCH {pattern}
        RETURN neighbor.id AS neighbor_id,
               neighbor.name AS neighbor_name,
               neighbor.entity_type AS neighbor_type,
               type(r) AS relation_type,
               r.description AS description,
               r.confidence AS confidence,
               r.evidence_text AS evidence_text,
               r.evidence_texts AS evidence_texts,
               r.source_doc AS source_doc,
               r.source_docs AS source_docs,
               r.source_chunk_id AS source_chunk_id,
               r.source_chunk_ids AS source_chunk_ids,
               r.source_url AS source_url,
               r.source_urls AS source_urls,
               r.source_authority AS source_authority,
               r.source_authorities AS source_authorities,
               r.collection_date AS collection_date,
               r.collection_dates AS collection_dates,
               r.severity AS severity,
               r.severities AS severities,
               r.metadata_json AS metadata_json,
               r.metadata_jsons AS metadata_jsons
        """
        results: List[Dict[str, Any]] = []
        with self.get_session() as session:
            for rec in session.run(cypher, id=entity_id):
                results.append(dict(rec))
        return results


# Global default instance
default_storage = GraphStorage()
