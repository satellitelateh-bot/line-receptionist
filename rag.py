import json
import os
import numpy as np
import ollama

EMBED_MODEL = "bge-m3"
KNOWLEDGE = "knowledge/shop.md"
INDEX = "index.json"


def load_chunks(path):
    chunks = []
    section = ""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## "):
                section = line[3:]
            elif line.startswith("- "):
                chunks.append(f"{section}: {line[2:]}")
    return chunks


def embed(texts):
    return ollama.embed(model=EMBED_MODEL, input=texts)["embeddings"]


def build_index():
    chunks = load_chunks(KNOWLEDGE)
    vectors = embed(chunks)
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump({"chunks": chunks, "vectors": vectors}, f, ensure_ascii=False)
    print(f"Indexed {len(chunks)} chunks")
    return chunks, np.array(vectors)


def load_index():
    if not os.path.exists(INDEX) or os.path.getmtime(INDEX) < os.path.getmtime(KNOWLEDGE):
        return build_index()
    with open(INDEX, encoding="utf-8") as f:
        data = json.load(f)
    return data["chunks"], np.array(data["vectors"])


CHUNKS, VECTORS = load_index()


def search(query, k=4):
    q = np.array(embed([query])[0])
    scores = VECTORS @ q / (np.linalg.norm(VECTORS, axis=1) * np.linalg.norm(q))
    best = np.argsort(scores)[::-1][:k]
    return [(CHUNKS[i], round(float(scores[i]), 3)) for i in best]


if __name__ == "__main__":
    for q in ["ตัดผมผู้หญิงเท่าไหร่", "Are you open on Wednesday?", "จอดรถได้ไหม", "Can I cancel my booking?"]:
        print("\nQ:", q)
        for text, score in search(q):
            print(f"  {score}  {text}")
