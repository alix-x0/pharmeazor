"""
Pharmeazor Knowledge Graph - Entity Normalizer
==============================================
Normalizes, disambiguates, canonicalizes, and deduplicates pharmaceutical
and clinical entities (DRUG, ACTIVE_INGREDIENT, DOSAGE_FORM, INDICATION,
CONTRAINDICATION, ADVERSE_EFFECT, INTERACTING_DRUG, POPULATION, LABORATORY,
DOSAGE_RULE) for the Pharmeazor GraphRAG knowledge graph.

Key Capabilities:
-----------------
1. Text & Diacritic Normalization: Unicode NFKD accent stripping, lowercasing,
   punctuation standardization.
2. Canonical Term Mapping: Maps synonyms, abbreviations, and language variants
   (French, English, Latin) to canonical medical concepts (e.g., Acetaminophen -> Paracétamol).
3. Pharmaceutical Form & Dosage Standardization: Canonical forms (Comprimé, Gélule, etc.)
   and uniform dosage units (g -> mg conversion).
4. Entity Deduplication & Resolution: Merges duplicate nodes from multi-document extraction,
   aggregating aliases and metadata.
5. Fuzzy Concept Resolution: Difflib-based similarity matching for query resolution
   and typo-tolerant entity linking.
"""

from __future__ import annotations

import difflib
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Augmentation.knowledge_graph.entity_extractor import (
    make_entity_id,
    normalize_string,
)
from ai_api.Augmentation.knowledge_graph.ontology import EntityType, KGEntity


# ==============================================================================
# CANONICAL THESAURUS & SYNONYM DICTIONARIES
# ==============================================================================

# 1. Target Active Ingredients (DCIs) with synonyms (French, English, trade synonyms)
CANONICAL_DCIS: Dict[str, str] = {
    # Paracetamol / Acetaminophen
    "paracetamol": "Paracétamol",
    "paracetamolum": "Paracétamol",
    "acetaminophen": "Paracétamol",
    "acetaminophene": "Paracétamol",
    "apap": "Paracétamol",

    # Ibuprofen
    "ibuprofene": "Ibuprofène",
    "ibuprofen": "Ibuprofène",
    "ibuprofenum": "Ibuprofène",

    # Aspirin / Acetylsalicylic Acid
    "aspirine": "Acide acétylsalicylique",
    "aspirin": "Acide acétylsalicylique",
    "acide acetylsalicylique": "Acide acétylsalicylique",
    "acetylsalicylic acid": "Acide acétylsalicylique",

    # Amoxicillin
    "amoxicilline": "Amoxicilline",
    "amoxicillin": "Amoxicilline",
    "amoxicilline trihydrate": "Amoxicilline",
    "amoxicilline sodique": "Amoxicilline",

    # Amoxicillin + Clavulanic Acid
    "amoxicilline acide clavulanique": "Amoxicilline + Acide clavulanique",
    "amoxicilline et acide clavulanique": "Amoxicilline + Acide clavulanique",
    "amoxicillin clavulanate": "Amoxicilline + Acide clavulanique",
    "co amoxiclav": "Amoxicilline + Acide clavulanique",
    "augmentin": "Amoxicilline + Acide clavulanique",

    # Omeprazole
    "omeprazole": "Oméprazole",
    "omeprazol": "Oméprazole",
    "omeprazole magnesique": "Oméprazole",

    # Metformin
    "metformine": "Metformine",
    "metformin": "Metformine",
    "metformine chlorhydrate": "Metformine",

    # Azithromycin
    "azithromycine": "Azithromycine",
    "azithromycin": "Azithromycine",
    "azithromycine dihydrate": "Azithromycine",

    # Ciprofloxacin
    "ciprofloxacine": "Ciprofloxacine",
    "ciprofloxacin": "Ciprofloxacine",
    "ciprofloxacine chlorhydrate": "Ciprofloxacine",

    # Diclofenac
    "diclofenac": "Diclofénac",
    "diclofenac sodique": "Diclofénac",
    "diclofenac potassique": "Diclofénac",

    # Metronidazole
    "metronidazole": "Métronidazole",
    "metronidazol": "Métronidazole",

    # Cefixime
    "cefixime": "Céfixime",
    "cefixime trihydrate": "Céfixime",

    # Ketoprofen
    "ketoprofene": "Kétoprofène",
    "ketoprofen": "Kétoprofène",

    # Pantoprazole
    "pantoprazole": "Pantoprazole",
    "pantoprazol": "Pantoprazole",

    # Esomeprazole
    "esomeprazole": "Ésoméprazole",
    "esomeprazol": "Ésoméprazole",

    # Cetirizine
    "cetirizine": "Cétirizine",
    "cetirizine dihydrochloride": "Cétirizine",
    "cetirizine dichlorhydrate": "Cétirizine",

    # Loratadine
    "loratadine": "Loratadine",

    # Prednisone / Prednisolone
    "prednisone": "Prednisone",
    "prednisolone": "Prednisolone",

    # Tramadol
    "tramadol": "Tramadol",
    "tramadol chlorhydrate": "Tramadol",

    # Codeine
    "codeine": "Codéine",
    "codeine phosphate": "Codéine",

    # Atorvastatin
    "atorvastatine": "Atorvastatine",
    "atorvastatin": "Atorvastatine",

    # Amlodipine
    "amlodipine": "Amlodipine",
    "amlodipine besilate": "Amlodipine",

    # Ramipril
    "ramipril": "Ramipril",

    # Bisoprolol
    "bisoprolol": "Bisoprolol",
    "bisoprolol fumarate": "Bisoprolol",

    # Salbutamol
    "salbutamol": "Salbutamol",
    "albuterol": "Salbutamol",

    # Phloroglucinol
    "phloroglucinol": "Phloroglucinol",
    "spasfon": "Phloroglucinol",

    # Diosmectite / Smectite
    "diosmectite": "Diosmectite",
    "smecta": "Diosmectite",

    # Loperamide
    "loperamide": "Lopéramide",
    "loperamide chlorhydrate": "Lopéramide",
}

# 2. Canonical Pharmaceutical Dosage Forms
CANONICAL_DOSAGE_FORMS: Dict[str, str] = {
    "comprime": "Comprimé",
    "comprimes": "Comprimé",
    "comp": "Comprimé",
    "cpr": "Comprimé",
    "cp": "Comprimé",
    "comprime pellicule": "Comprimé pelliculé",
    "comprime effervescent": "Comprimé effervescent",
    "comprime secable": "Comprimé sécable",
    "comprime orodispersible": "Comprimé orodispersible",
    "comprime a liberaton prolongee": "Comprimé à libération prolongée",
    "comprime lp": "Comprimé à libération prolongée",
    "gelule": "Gélule",
    "gelules": "Gélule",
    "gel": "Gélule",
    "sirop": "Sirop",
    "solution buvable": "Solution buvable",
    "sol buv": "Solution buvable",
    "suspension buvable": "Suspension buvable",
    "susp buv": "Suspension buvable",
    "poudre pour suspension buvable": "Poudre pour suspension buvable",
    "sachet": "Poudre pour solution en sachet",
    "sachets": "Poudre pour solution en sachet",
    "solution injectable": "Solution injectable",
    "sol inj": "Solution injectable",
    "injectable": "Solution injectable",
    "suppositoire": "Suppositoire",
    "suppo": "Suppositoire",
    "suppositoires": "Suppositoire",
    "pommade": "Pommade",
    "creme": "Crème",
    "collyre": "Collyre",
    "spray": "Spray",
    "aerosol": "Aérosol pour inhalation",
}

# 3. Canonical Clinical Indications & Symptoms
CANONICAL_INDICATIONS: Dict[str, str] = {
    "cephalee": "Céphalée",
    "cephalees": "Céphalée",
    "mal de tete": "Céphalée",
    "maux de tete": "Céphalée",
    "migraine": "Migraine",
    "migraines": "Migraine",
    "fievre": "Fièvre",
    "etats febriles": "Fièvre",
    "etat febrile": "Fièvre",
    "hyperthermie": "Fièvre",
    "douleur": "Douleur",
    "douleurs": "Douleur",
    "douleurs dentaires": "Douleur dentaire",
    "rage de dent": "Douleur dentaire",
    "courbatures": "Courbatures",
    "douleurs musculaires": "Myalgie",
    "myalgie": "Myalgie",
    "myalgies": "Myalgie",
    "douleurs articulaires": "Arthralgie",
    "arthralgie": "Arthralgie",
    "arthrose": "Arthrose",
    "rhinite": "Rhinite",
    "rhume": "Rhinite",
    "rhinopharyngite": "Rhinopharyngite",
    "etat grippal": "Syndrome grippal",
    "syndrome grippal": "Syndrome grippal",
    "grippe": "Grippe",
    "toux": "Toux",
    "toux seche": "Toux sèche",
    "toux grasse": "Toux grasse",
    "infection bacterienne": "Infection bactérienne",
    "angine": "Angine bactérienne",
    "otite": "Otite",
    "sinusite": "Sinusite",
    "hypertension": "Hypertension artérielle",
    "hypertension arterielle": "Hypertension artérielle",
    "reflux gastro oesophagien": "Reflux gastro-œsophagien",
    "rgo": "Reflux gastro-œsophagien",
    "brulures d estomac": "Brûlures d'estomac",
    "pyrosis": "Pyrosis",
    "diarrhee": "Diarrhée",
    "diarrhee aigue": "Diarrhée aiguë",
    "diabete de type 2": "Diabète de type 2",
}

# 4. Canonical Contraindications & Clinical Risk Conditions
CANONICAL_CONTRAINDICATIONS: Dict[str, str] = {
    "insuffisance hepatique": "Insuffisance hépatocellulaire",
    "insuffisance hepatocellulaire": "Insuffisance hépatocellulaire",
    "insuffisance hepatique severe": "Insuffisance hépatocellulaire sévère",
    "insuffisance renale": "Insuffisance rénale",
    "insuffisance renale severe": "Insuffisance rénale sévère",
    "hypersensibilite au paracetamol": "Allergie au paracétamol",
    "allergie au paracetamol": "Allergie au paracétamol",
    "hypersensibilite a la substance active": "Hypersensibilité à la substance active",
    "ulcere gastro duodenal": "Ulcère gastro-duodénal évolutif",
    "ulcere peptique": "Ulcère gastro-duodénal évolutif",
    "hemorragie gastro intestinale": "Hémorragie gastro-intestinale",
    "grossesse au dela du 5eme mois": "Grossesse (> 5ème mois / 24 SA)",
    "grossesse 3eme trimestre": "Grossesse (> 5ème mois / 24 SA)",
    "allaitement": "Allaitement",
    "enfant de moins de 15 ans": "Enfant < 15 ans",
    "enfant de moins de 50 kg": "Poids inférieur à 50 kg",
    "poids inferieur a 50 kg": "Poids inférieur à 50 kg",
    "phenycetonurie": "Phénylcétonurie",
    "phenylcetonurie": "Phénylcétonurie",
    "deficit en g6pd": "Déficit en G6PD",
}

# 5. Canonical Special Populations
CANONICAL_POPULATIONS: Dict[str, str] = {
    "adulte": "Adulte",
    "adultes": "Adulte",
    "enfant": "Enfant",
    "enfants": "Enfant",
    "nourrisson": "Nourrisson",
    "sujet age": "Personne âgée (> 65 ans)",
    "personne agee": "Personne âgée (> 65 ans)",
    "femme enceinte": "Grossesse",
    "grossesse": "Grossesse",
    "femme allaitante": "Allaitement",
    "patient de moins de 50 kg": "Patient < 50 kg",
    "patient pesant au moins 50 kg": "Patient >= 50 kg",
    "insuffisant renal": "Insuffisant rénal",
    "insuffisant hepatique": "Insuffisant hépatique",
}

# 6. Canonical Laboratories (Manufacturers operating in Algeria)
CANONICAL_LABORATORIES: Dict[str, str] = {
    "biopharm": "BIOPHARM",
    "biopharm spa": "BIOPHARM",
    "laboratoires biopharm": "BIOPHARM",
    "saidal": "SAIDAL",
    "groupe saidal": "SAIDAL",
    "inpha medis": "INPHA-MÉDIS",
    "inpha medis algerie": "INPHA-MÉDIS",
    "sanofi": "SANOFI",
    "sanofi aventis algerie": "SANOFI",
    "sanofi algerie": "SANOFI",
    "propharmal": "PROPHARMAL",
    "propharmal spa": "PROPHARMAL",
    "laboratoire propharmal": "PROPHARMAL",
    "hikma": "HIKMA PHARMACEUTICALS",
    "hikma algerie": "HIKMA PHARMACEUTICALS",
    "dar al dawa": "DAR AL DAWA",
    "dar al dawa algerie": "DAR AL DAWA",
    "pharmalliance": "PHARMALLIANCE",
    "frater razes": "FRATER-RAZES",
    "laboratoires frater razes": "FRATER-RAZES",
    "merinal": "MERINAL",
    "laboratoires merinal": "MERINAL",
    "novartis": "NOVARTIS",
    "gsk": "GLAXOSMITHKLINE",
    "glaxosmithkline": "GLAXOSMITHKLINE",
    "upsa": "UPSA",
    "upsa sas": "UPSA",
}


# ==============================================================================
# ENTITY NORMALIZER IMPLEMENTATION
# ==============================================================================

class EntityNormalizer:
    """
    Standardizes, disambiguates, and resolves entities for the pharmaceutical
    knowledge graph. Ensures consistency between free-text clinical extractions
    and canonical medical nomenclature.
    """

    def __init__(self, similarity_threshold: float = 0.82):
        self.similarity_threshold = similarity_threshold

        # Fast lookup mapping: EntityType -> Dict[normalized_token_key, canonical_name]
        self._thesaurus: Dict[EntityType, Dict[str, str]] = {
            EntityType.ACTIVE_INGREDIENT: CANONICAL_DCIS,
            EntityType.DOSAGE_FORM: CANONICAL_DOSAGE_FORMS,
            EntityType.INDICATION: CANONICAL_INDICATIONS,
            EntityType.CONTRAINDICATION: CANONICAL_CONTRAINDICATIONS,
            EntityType.POPULATION: CANONICAL_POPULATIONS,
            EntityType.LABORATORY: CANONICAL_LABORATORIES,
        }

        # Inverted index for reverse search / alias lookup
        self._canonical_to_keys: Dict[EntityType, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        for etype, mapping in self._thesaurus.items():
            for key, canonical in mapping.items():
                self._canonical_to_keys[etype][canonical].add(key)

    # --------------------------------------------------------------------------
    # Text and Unit Normalization
    # --------------------------------------------------------------------------

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Removes diacritics, lowercases, replaces non-alphanumeric chars with
        single spaces, and trims whitespace.
        """
        if not text:
            return ""
        nfkd = unicodedata.normalize("NFKD", text)
        no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
        cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", no_accents.lower()).strip()
        return cleaned

    @staticmethod
    def parse_dosage_value_mg(text: str) -> Optional[float]:
        """
        Extracts and converts dosage values to milligrams (mg).
        Examples:
            '1000 mg' -> 1000.0
            '1 g'     -> 1000.0
            '500mg'   -> 500.0
            '0.5 g'   -> 500.0
            '500 µg'  -> 0.5
        """
        if not text:
            return None

        # Look for pattern: <number> <unit>
        match = re.search(r"(\d+(?:[\.,]\d+)?)\s*(mg|g|mcg|µg|ug)\b", text, flags=re.I)
        if not match:
            return None

        val_str = match.group(1).replace(",", ".")
        unit = match.group(2).lower()
        try:
            val = float(val_str)
        except ValueError:
            return None

        if unit == "g":
            return val * 1000.0
        elif unit in ("mcg", "µg", "ug"):
            return val / 1000.0
        elif unit == "mg":
            return val

        return None

    def normalize_dosage_form_string(self, text: str) -> str:
        """
        Standardizes a dosage form string (e.g. '1000 mg cpr pelliculé' -> '1000 mg Comprimé pelliculé').
        """
        if not text:
            return ""

        cleaned = text.strip()
        cleaned_norm = self.clean_text(cleaned)

        # Standardize dosage unit presentation: '1000mg' -> '1000 mg', '1g' -> '1 g'
        standardized = re.sub(r"(\d+)\s*(mg|g|ml|ui)\b", r"\1 \2", cleaned, flags=re.I)

        # Replace matched form abbreviation with canonical form
        for abbr, canonical in CANONICAL_DOSAGE_FORMS.items():
            pattern = rf"\b{re.escape(abbr)}\b"
            if re.search(pattern, cleaned_norm):
                # If the string is purely the form abbreviation, return canonical form
                if cleaned_norm == abbr:
                    return canonical
                # Otherwise, substitute
                standardized = re.sub(pattern, canonical, standardized, flags=re.I)
                break

        return standardized.strip()

    # --------------------------------------------------------------------------
    # Canonical Resolution
    # --------------------------------------------------------------------------

    def resolve_canonical_name(self, name: str, entity_type: EntityType) -> str:
        """
        Resolves a raw entity name into its canonical dictionary name if available.
        Fallback to clean capitalized name.
        """
        if not name:
            return ""

        clean_norm = self.clean_text(name)
        mapping = self._thesaurus.get(entity_type, {})

        # 1. Exact match in normalized thesaurus
        if clean_norm in mapping:
            return mapping[clean_norm]

        # 2. Check for substring match in known DCIs / Forms / Indications
        for norm_key, canonical in mapping.items():
            if len(norm_key) >= 4 and norm_key == clean_norm:
                return canonical

        # 3. Fuzzy match against dictionary keys
        if mapping:
            matches = difflib.get_close_matches(
                clean_norm,
                list(mapping.keys()),
                n=1,
                cutoff=self.similarity_threshold,
            )
            if matches:
                return mapping[matches[0]]

        # 4. Default formatting: clean string with title casing or uppercase for lab/brand
        if entity_type in (EntityType.DRUG, EntityType.LABORATORY):
            return name.strip().upper()
        return name.strip().capitalize()

    def get_canonical_id(self, entity_type: EntityType, name: str) -> str:
        """
        Builds a canonical, collision-resistant ID based on the canonicalized name.
        """
        canonical_name = self.resolve_canonical_name(name, entity_type)
        return make_entity_id(entity_type, canonical_name)

    # --------------------------------------------------------------------------
    # Entity-level Normalization
    # --------------------------------------------------------------------------

    def normalize_entity(self, entity: KGEntity) -> KGEntity:
        """
        Normalizes a single KGEntity:
        - Resolves canonical name and ID.
        - Preserves original raw name in aliases.
        - Enriches metadata with normalization info.
        """
        canon_name = self.resolve_canonical_name(entity.name, entity.entity_type)
        canon_id = make_entity_id(entity.entity_type, canon_name)

        # Collect unique aliases
        aliases: Set[str] = set(entity.aliases)
        aliases.add(entity.name)
        aliases.add(canon_name)
        aliases.add(canon_name.lower())
        aliases.add(canon_name.upper())

        # Clean metadata
        meta = dict(entity.metadata)
        meta["raw_name"] = entity.name
        meta["canonicalized"] = True

        # For dosage form entities, parse quantitative dose if present
        if entity.entity_type == EntityType.DOSAGE_FORM:
            dose_mg = self.parse_dosage_value_mg(entity.name)
            if dose_mg is not None:
                meta["dose_mg"] = dose_mg

        return KGEntity(
            id=canon_id,
            name=canon_name,
            entity_type=entity.entity_type,
            aliases=sorted(list(aliases)),
            metadata=meta,
        )

    # --------------------------------------------------------------------------
    # Multi-Entity Merging & Deduplication
    # --------------------------------------------------------------------------

    def deduplicate_entities(self, entities: Iterable[KGEntity]) -> List[KGEntity]:
        """
        Merges entities that share the same canonical ID into a single canonical node.
        Combines aliases and aggregates document occurrences in metadata.
        """
        clustered: Dict[str, List[KGEntity]] = defaultdict(list)

        # Normalize and group by canonical ID
        for ent in entities:
            norm_ent = self.normalize_entity(ent)
            clustered[norm_ent.id].append(norm_ent)

        merged_entities: List[KGEntity] = []

        for cid, group in clustered.items():
            if len(group) == 1:
                merged_entities.append(group[0])
                continue

            # Merge multiple nodes
            base = group[0]
            combined_aliases: Set[str] = set()
            combined_sources: Set[str] = set()
            combined_drug_ids: Set[str] = set()
            merged_meta: Dict[str, Any] = dict(base.metadata)

            for item in group:
                combined_aliases.update(item.aliases)
                if "source" in item.metadata and item.metadata["source"]:
                    combined_sources.add(str(item.metadata["source"]))
                if "drug_id" in item.metadata and item.metadata["drug_id"]:
                    combined_drug_ids.add(str(item.metadata["drug_id"]))

            merged_meta["occurrence_count"] = len(group)
            if combined_sources:
                merged_meta["sources"] = sorted(list(combined_sources))
            if combined_drug_ids:
                merged_meta["drug_ids"] = sorted(list(combined_drug_ids))

            merged_entities.append(
                KGEntity(
                    id=cid,
                    name=base.name,
                    entity_type=base.entity_type,
                    aliases=sorted(list(combined_aliases)),
                    metadata=merged_meta,
                )
            )

        return merged_entities

    # --------------------------------------------------------------------------
    # Query & Mention Resolution
    # --------------------------------------------------------------------------

    def resolve_mention(
        self,
        mention: str,
        expected_type: Optional[EntityType] = None,
    ) -> Optional[Tuple[str, EntityType, float]]:
        """
        Attempts to resolve an arbitrary user query string or mention
        to a canonical entity name, entity type, and confidence score.
        Returns: (canonical_name, entity_type, confidence) or None.
        """
        clean_norm = self.clean_text(mention)
        if not clean_norm:
            return None

        types_to_check = [expected_type] if expected_type else list(self._thesaurus.keys())

        # 1. Exact thesaurus check
        for etype in types_to_check:
            mapping = self._thesaurus.get(etype, {})
            if clean_norm in mapping:
                return mapping[clean_norm], etype, 1.0

        # 2. Fuzzy match against thesaurus
        best_candidate: Optional[str] = None
        best_type: Optional[EntityType] = None
        best_ratio: float = 0.0

        for etype in types_to_check:
            mapping = self._thesaurus.get(etype, {})
            for key, canon in mapping.items():
                ratio = difflib.SequenceMatcher(None, clean_norm, key).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_candidate = canon
                    best_type = etype

        if best_candidate and best_type and best_ratio >= self.similarity_threshold:
            return best_candidate, best_type, round(best_ratio, 3)

        return None


# Global default instance for convenience
default_normalizer = EntityNormalizer()
