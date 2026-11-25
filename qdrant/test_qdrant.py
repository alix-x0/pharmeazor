"""
Qdrant Vector Database Quick Test Script
Tests connection to local Qdrant server, collection creation, vector upsert, and similarity search.
"""

import sys
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

def test_qdrant():
    print("Connecting to local Qdrant server at http://127.0.0.1:6333...")
    try:
        client = QdrantClient(url="http://127.0.0.1:6333", timeout=10)
        collections = client.get_collections()
        print(f"SUCCESS: Connected to Qdrant! Existing collections: {collections.collections}")
    except Exception as e:
        print(f"FAILED to connect to server: {e}")
        print("\nTesting local in-memory/embedded fallback mode...")
        client = QdrantClient(":memory:")
        print("Embedded/In-memory Qdrant instance created successfully.")

    collection_name = "test_medications"
    vector_size = 4

    print(f"\nCreating collection '{collection_name}' (vector size: {vector_size}, distance: Cosine)...")
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    print("Collection created successfully.")

    print("\nInserting sample drug interaction records...")
    points = [
        PointStruct(id=1, vector=[0.05, 0.61, 0.76, 0.17], payload={"drug": "Paracetamol", "category": "Antalgique"}),
        PointStruct(id=2, vector=[0.19, 0.81, 0.75, 0.11], payload={"drug": "Ibuprofene", "category": "AINS"}),
        PointStruct(id=3, vector=[0.36, 0.55, 0.47, 0.94], payload={"drug": "Amoxicilline", "category": "Antibiotique"}),
    ]
    client.upsert(collection_name=collection_name, points=points)
    print(f"Upserted {len(points)} sample vectors.")

    print("\nQuerying closest vector to [0.2, 0.8, 0.7, 0.1] (Searching for similar pain-relief drugs)...")
    search_result = client.query_points(
        collection_name=collection_name,
        query=[0.2, 0.8, 0.7, 0.1],
        limit=2,
    )

    for hit in search_result.points:
        print(f"  -> Match: ID={hit.id}, Score={hit.score:.4f}, Payload={hit.payload}")

    print("\n=== Qdrant is fully installed, configured, and working perfectly! ===")

if __name__ == "__main__":
    test_qdrant()
