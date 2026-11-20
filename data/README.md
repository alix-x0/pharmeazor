# Pharmeazor Drug Knowledge Base (RAG Corpus)

Ce dossier contient la base de connaissances pharmaceutique officielle (ANPP - Algérie) intégrée pour alimenter le système **RAG (Retrieval-Augmented Generation)** de Pharmeazor.

---

## 1. Vue d'ensemble des Données

- **Source principale** : Agence Nationale des Produits Pharmaceutiques (ANPP - Algérie) + notices officielles.
- **Classes thérapeutiques (DCI)** : 40 dossiers majeurs (paracétamol, ibuprofène, amoxicilline, tramadol, amlodipine, etc.).
- **Documents totaux** : **989 monographies** complètes.
  - **RCP** (Résumé des Caractéristiques du Produit - professionnels de santé) : ~462
  - **Notices** (destinées aux patients) : ~432
- **Marques commerciales uniques** : +518 médicaments enregistrés en Algérie (Doliprane, Algésic, Clamoxyl, Acupan, Aldomet, etc.).
- **Formats disponibles** :
  - `.json` : Métadonnées complètes + sections cliniques structurées (indications, contre-indications, posologie, interactions, effets indésirables, etc.).
  - `.md` : Textes en Markdown avec titres de sections standardisés.

---

## 2. Structure des Dossiers

```text
data/
├── __init__.py                # Package Python
├── loader.py                  # DrugCorpusLoader & RAGChunk generator
├── inspect_corpus.py          # Script de test & inspection (python data/inspect_corpus.py)
├── README.md                  # Ce guide
└── outputs_data/               # 1,983 fichiers (JSON + MD) et fichiers de synthèse
    ├── LIRE_MOI.txt           # Synthèse du filtrage
    ├── _MANIFESTE.csv         # Décisions d'audit (1,320 lignes)
    ├── _RESUME.csv            # Synthèse par DCI (40 dossiers)
    ├── _EXCLUS.csv            # Fichiers exclus
    ├── _COMBINAISONS_HORS_LISTE.csv
    ├── 01_paracetamol/
    │   ├── 1_1/
    │   │   ├── 001_DOLIPRANE.json
    │   │   ├── 001_DOLIPRANE.md
    │   │   └── ...
    ├── 02_ibuprofene/
    └── ... (jusqu'à 40_methyldopa)
```

---

## 3. Utilisation Rapide (`data/loader.py`)

### A. Charger la base de données
```python
from data.loader import DrugCorpusLoader

loader = DrugCorpusLoader()
print(f"Total documents: {len(loader)}") # 989

# Filtrer par DCI ou marque
doliprane_docs = loader.filter(brand="DOLIPRANE")
for doc in doliprane_docs:
    print(doc.brand, doc.doc_type, doc.lab)
    
    # Accéder à une section clinique précise
    interactions = doc.get_section("interactions")
    if interactions and not interactions.is_empty():
        print("Interactions:", interactions.text[:200])
```

### B. Générer des Chunks RAG prêts pour Vector DB
Le loader génère des chunks découpés **par section clinique** (ce qui évite de mélanger les indications et les contre-indications) avec un en-tête contextuel et des métadonnées riches.

```python
from data.loader import DrugCorpusLoader

loader = DrugCorpusLoader()

# Générer les chunks (~30,000 chunks)
chunks = loader.get_rag_chunks(
    min_chars=60,
    max_chunk_chars=1200,
    overlap_chars=150
)

sample = chunks[0]
print(sample.text)
# Sortie :
# Médicament: DOLIPRANE | DCI: PARACÉTAMOL | Forme/Lab: PROPHARMAL SPA | Section: Contre-indications
# 4.3 Contre-indications :
# • Hypersensibilité au paracétamol...

print(sample.metadata)
# {
#   'brand': 'DOLIPRANE',
#   'dci': 'PARACÉTAMOL',
#   'lab': 'PROPHARMAL SPA',
#   'doc_type': 'rcp',
#   'section_key': 'contre_indications',
#   'url': 'https://rcp.anpp.dz/...',
#   ...
# }
```

### C. Exporter en JSONL (pour fine-tuning ou ingestion batch)
```python
loader.export_chunks_jsonl("data/rag_chunks.jsonl")
```

---

## 4. Exemples d'Intégration RAG pour votre Équipe

### Exemple 1 : ChromaDB
```python
import chromadb
from data.loader import DrugCorpusLoader

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="pharmeazor_drugs")

loader = DrugCorpusLoader()
chunks = loader.get_rag_chunks()

# Insertion par batch
BATCH_SIZE = 500
for i in range(0, len(chunks), BATCH_SIZE):
    batch = chunks[i : i + BATCH_SIZE]
    collection.add(
        ids=[f"chunk_{i + j}" for j in range(len(batch))],
        documents=[c.text for c in batch],
        metadatas=[c.metadata for c in batch],
    )
```

### Exemple 2 : LangChain
```python
from langchain_core.documents import Document
from data.loader import DrugCorpusLoader

loader = DrugCorpusLoader()
chunks = loader.get_rag_chunks()

langchain_docs = [
    Document(page_content=c.text, metadata=c.metadata)
    for c in chunks
]
# Ensuite: FAISS.from_documents(langchain_docs, embeddings)
```

---

## 5. Vérification
Pour tester à tout moment l'intégrité des données :
```powershell
python data/inspect_corpus.py
```

