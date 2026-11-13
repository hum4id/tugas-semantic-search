"""
Menjalankan seluruh eksperimen wajib terhadap API yang benar-benar berjalan.

Cara pakai (dari folder root project, venv aktif):
    python experiments/run_experiments.py

Script ini akan:
1. Menyalakan server uvicorn di port 8011 (log -> experiments/server.log)
2. Memanggil POST /index
3. Menjalankan Experiment 1 (semantic search), 2 (Top-K), 3 (bad retrieval candidates)
4. Menyimpan actual request/response ke experiments/results.json dan experiments/results.md
5. Mematikan server

Pastikan tidak ada server lain (fastapi dev) yang sedang memakai folder qdrant_data,
karena Qdrant local mode hanya bisa dibuka oleh satu proses.
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent
PORT = 8011
BASE_URL = f"http://127.0.0.1:{PORT}"

# Query natural, sengaja tidak menyalin kata kunci dari dataset.
EXPERIMENT_1_QUERIES = [
    "sup berwarna hitam pekat dari Jawa Timur",
    "minuman yang cocok diminum ketika masuk angin",
    "jajanan manis yang isinya meleleh di mulut",
    "olahan ikan dari Palembang yang dicocol saus asam",
    "lauk daging yang awet karena dimasak sampai kering",
    "kudapan yang terbuat dari ubi kayu",
    "spicy grilled chicken from Lombok",
]

TOP_K_QUERY = "minuman tradisional yang disajikan hangat"
TOP_K_VALUES = [1, 3, 5]

BAD_RETRIEVAL_CANDIDATES = [
    "minuman dingin yang tidak memakai santan",
    "makanan yang sama sekali tidak pedas",
    "makanan khas Kalimantan",
    "cara memperbaiki laptop yang tidak mau menyala",
    "soto",
]


def wait_for_server(timeout: int = 900) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = httpx.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                return response.json()
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise TimeoutError("Server tidak siap. Cek experiments/server.log")


def post(path: str, payload: dict) -> dict:
    response = httpx.post(f"{BASE_URL}{path}", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def main():
    log_file = open(OUT_DIR / "server.log", "w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", str(PORT)],
        cwd=ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    print("Menyalakan server (run pertama akan mendownload model, bisa beberapa menit)...")

    results = {"generated_at": datetime.now().isoformat(timespec="seconds")}
    try:
        results["health_before_index"] = wait_for_server()
        print("Server siap. Indexing dataset...")

        index_request = {"recreate": True}
        results["index"] = {"request": index_request, "response": post("/index", index_request)}
        results["health_after_index"] = httpx.get(f"{BASE_URL}/health").json()

        print("Experiment 1...")
        results["experiment_1"] = []
        for query in EXPERIMENT_1_QUERIES:
            request = {"query": query, "top_k": 3}
            results["experiment_1"].append({"request": request, "response": post("/search", request)})

        print("Experiment 2...")
        results["experiment_2"] = []
        for k in TOP_K_VALUES:
            request = {"query": TOP_K_QUERY, "top_k": k}
            results["experiment_2"].append({"request": request, "response": post("/search", request)})

        print("Experiment 3...")
        results["experiment_3"] = []
        for query in BAD_RETRIEVAL_CANDIDATES:
            request = {"query": query, "top_k": 3}
            results["experiment_3"].append({"request": request, "response": post("/search", request)})

        # Bonus: contoh filter payload category
        request = {"query": "minuman tradisional yang disajikan hangat", "top_k": 3, "category": "minuman"}
        results["bonus_category_filter"] = {"request": request, "response": post("/search", request)}

        # Bonus: error handling ketika top_k tidak valid
        bad = httpx.post(f"{BASE_URL}/search", json={"query": "soto", "top_k": 0})
        results["bonus_validation_error"] = {"status_code": bad.status_code, "body": bad.json()}
    finally:
        server.terminate()
        try:
            server.wait(timeout=20)
        except subprocess.TimeoutExpired:
            server.kill()
        log_file.close()

    (OUT_DIR / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(results)
    print("Selesai. Hasil: experiments/results.json dan experiments/results.md")


def format_results(response: dict) -> str:
    lines = []
    for rank, item in enumerate(response["results"], start=1):
        lines.append(f"{rank}. **{item['name']}** ({item['category']}) - score `{item['score']}`")
    return "\n".join(lines)


def write_markdown(results: dict):
    parts = [f"# Raw Experiment Results\n\nGenerated: {results['generated_at']}\n"]
    parts.append(f"## Index\n\n```json\n{json.dumps(results['index']['response'], ensure_ascii=False, indent=2)}\n```\n")
    for title, key in [
        ("Experiment 1", "experiment_1"),
        ("Experiment 2", "experiment_2"),
        ("Experiment 3 candidates", "experiment_3"),
    ]:
        parts.append(f"## {title}\n")
        for run in results[key]:
            request = run["request"]
            parts.append(f"### `{request['query']}` (top_k={request['top_k']})\n\n{format_results(run['response'])}\n")
    (OUT_DIR / "results.md").write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
