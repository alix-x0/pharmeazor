# Qdrant Vector Database in Project RCR

This directory contains the standalone **Qdrant Vector Database** (`v1.20.2`) installed locally for **Project RCR / Pharmeazor**.

---

## 🚀 How to Run Qdrant

### Option 1: Standalone Native Server (Recommended on Windows)
Simply double-click:
```
start-qdrant.bat
```
Or run from PowerShell / Command Prompt:
```powershell
cd "c:\Users\dell\Desktop\project RCR\qdrant"
.\qdrant.exe --config-path config/config.yaml
```

Once started:
- 🖥️ **Web Dashboard UI**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- 🌐 **REST API**: `http://localhost:6333`
- ⚡ **gRPC API**: `localhost:6334`
- 💾 **Storage Location**: `project RCR\qdrant\storage`

---

### Option 2: Docker Compose
If you have Docker Desktop running:
```powershell
cd "c:\Users\dell\Desktop\project RCR\qdrant"
docker-compose up -d
```

---

### Option 3: Python Embedded Mode (No Server Needed)
You can also use Qdrant directly inside your Python backend without running any server:
```python
from qdrant_client import QdrantClient

# Embedded storage directly in the project folder:
client = QdrantClient(path="c:/Users/dell/Desktop/project RCR/qdrant/storage")
```

---

## 🐍 Python Usage Example

The Python SDK `qdrant-client` is installed. Run the test script to verify:
```powershell
python "c:\Users\dell\Desktop\project RCR\qdrant\test_qdrant.py"
```

### Basic Code Example:
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Connect to running server
client = QdrantClient(url="http://localhost:6333")

# Create collection
client.create_collection(
    collection_name="drug_interactions",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)

# Insert vectors
client.upsert(
    collection_name="drug_interactions",
    points=[
        PointStruct(id=1, vector=[...], payload={"dci": "Paracetamol"}),
    ]
)

# Search
results = client.query_points(
    collection_name="drug_interactions",
    query=[...],
    limit=5
)
```

---

## 📁 Directory Structure
```
project RCR/qdrant/
├── qdrant.exe             # Native Qdrant binary
├── start-qdrant.bat       # Quick launcher script
├── docker-compose.yml     # Docker setup
├── test_qdrant.py         # Verification & example script
├── config/
│   └── config.yaml        # Service and storage configuration
├── static/                # Official Qdrant Web UI Dashboard
├── storage/               # Vector data files and indexes
└── snapshots/             # Database backups / snapshots
```
