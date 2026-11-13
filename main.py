"""
Semantic Search API - Kuliner Nusantara

Flow indexing : data.json -> SentenceTransformer -> vector -> Qdrant (vector + payload)
Flow search   : query -> SentenceTransformer -> query vector -> Qdrant -> Top-K hasil
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data.json"
QDRANT_PATH = BASE_DIR / "qdrant_data"
COLLECTION_NAME = "kuliner_nusantara"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Diisi saat startup (lifespan) supaya model hanya di-load sekali.
state: dict = {}


def load_dataset() -> list[dict]:
    with open(DATA_PATH, encoding="utf-8") as file:
        documents = json.load(file)

    for index, doc in enumerate(documents):
        if not doc.get("text") or not doc.get("category"):
            raise ValueError(f"Data index {index} wajib punya field 'text' dan 'category'.")
    return documents


def get_vector_size(model: SentenceTransformer) -> int:
    size = model.get_sentence_embedding_dimension()
    if size is None:
        size = len(model.encode("test"))
    return int(size)


@asynccontextmanager
async def lifespan(app: FastAPI):
    model = SentenceTransformer(MODEL_NAME)
    state["model"] = model
    state["vector_size"] = get_vector_size(model)
    state["client"] = QdrantClient(path=str(QDRANT_PATH))
    yield
    state["client"].close()


app = FastAPI(
    title="Semantic Search Kuliner Nusantara",
    description="Semantic search berbasis SentenceTransformers dan Qdrant.",
    lifespan=lifespan,
)


class IndexRequest(BaseModel):
    recreate: bool = Field(
        default=True,
        description="Hapus collection lama sebelum indexing agar tidak ada data ganda.",
    )


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, examples=["minuman hangat saat cuaca dingin"])
    top_k: int = Field(default=3, ge=1, le=50)
    category: Optional[str] = Field(
        default=None,
        description="Opsional: filter berdasarkan payload category.",
    )


def collection_ready(client: QdrantClient) -> bool:
    if not client.collection_exists(COLLECTION_NAME):
        return False
    return client.count(COLLECTION_NAME).count > 0


@app.get("/health")
def health():
    client: QdrantClient = state["client"]
    exists = client.collection_exists(COLLECTION_NAME)
    points = client.count(COLLECTION_NAME).count if exists else 0
    return {
        "status": "OK",
        "model": MODEL_NAME,
        "vector_size": state["vector_size"],
        "collection": COLLECTION_NAME,
        "collection_exists": exists,
        "indexed_points": points,
    }


@app.post("/index")
def index_dataset(request: IndexRequest = IndexRequest()):
    client: QdrantClient = state["client"]
    model: SentenceTransformer = state["model"]

    try:
        documents = load_dataset()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=500, detail=f"Gagal membaca dataset: {error}")

    if request.recreate and client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=state["vector_size"],
                distance=Distance.COSINE,
            ),
        )

    texts = [doc["text"] for doc in documents]
    vectors = model.encode(texts, batch_size=32, show_progress_bar=False)

    points = [
        PointStruct(
            id=index,  # ID deterministik: indexing ulang menimpa data yang sama
            vector=vector.tolist(),
            payload={
                "name": doc.get("name"),
                "text": doc["text"],
                "category": doc["category"],
                "region": doc.get("region"),
            },
        )
        for index, (doc, vector) in enumerate(zip(documents, vectors))
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)

    categories = sorted({doc["category"] for doc in documents})
    return {
        "message": "Dataset berhasil di-index ke Qdrant.",
        "indexed": len(points),
        "categories": categories,
        "vector_size": state["vector_size"],
    }


@app.post("/search")
def search(request: SearchRequest):
    client: QdrantClient = state["client"]
    model: SentenceTransformer = state["model"]

    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query tidak boleh kosong.")

    if not collection_ready(client):
        raise HTTPException(
            status_code=400,
            detail="Dataset belum di-index. Jalankan POST /index terlebih dahulu.",
        )

    query_filter = None
    if request.category:
        query_filter = Filter(
            must=[FieldCondition(key="category", match=MatchValue(value=request.category))]
        )

    query_vector = model.encode(query).tolist()
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=request.top_k,
        query_filter=query_filter,
        with_payload=True,
    )

    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append(
            {
                "id": point.id,
                "name": payload.get("name"),
                "text": payload.get("text"),
                "category": payload.get("category"),
                "region": payload.get("region"),
                "score": round(float(point.score), 4),
            }
        )

    return {
        "query": query,
        "top_k": request.top_k,
        "category_filter": request.category,
        "results": results,
    }
