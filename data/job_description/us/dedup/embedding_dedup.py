# type: ignore

import os
import json
import time
import logging
import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)


def load_embed_cache(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_embed_cache(cache: dict, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(cache, f)


def get_embeddings_google(
    texts: list[str],
    api_key: str,
    model: str,
) -> list[list[float]]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:batchEmbedContents?key={api_key}"
    )
    embed_requests = [
        {"model": f"models/{model}", "content": {"parts": [{"text": t}]}}
        for t in texts
    ]
    response = requests.post(url, json={"requests": embed_requests}, timeout=30)
    response.raise_for_status()
    data = response.json()
    return [item["values"] for item in data["embeddings"]]


def make_fingerprint(row: dict) -> str:
    title   = str(row.get("job_title", "")).strip().lower()
    company = str(row.get("company", "")).strip().lower()
    loc     = str(row.get("location", "")).strip().lower()
    return f"{title} | {company} | {loc}"


def jaccard_tokens(text_a: str, text_b: str) -> float:
    if not text_a or not text_b:
        return 0.0
    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def pick_richer_job(job_a: dict, job_b: dict) -> tuple[dict, dict]:
    def score(job):
        s = min(len(str(job.get("full_description", ""))), 3000)
        if job.get("salary_min") or job.get("salary_min_raw"):
            s += 500
        if job.get("skills"):
            s += len(str(job.get("skills", "")).split(",")) * 50
        if job.get("source") == "LinkedIn":
            s += 100
        return s

    if score(job_a) >= score(job_b):
        return job_a, job_b
    return job_b, job_a


def embed_with_retry(texts, api_key, model, max_retries=3):
    """Call embedding API with exponential backoff on 429."""
    for attempt in range(max_retries):
        try:
            return get_embeddings_google(texts, api_key, model)
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 60 * (attempt + 1)  # 60s, 120s, 180s
                logger.warning(f"Rate limited — waiting {wait}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait)
            else:
                raise
    return None


def deduplicate_jobs(
    df: pd.DataFrame,
    google_api_key: str,
    similarity_threshold: float,
    description_overlap: float,
    embed_cache_path: str,
    embed_model: str = "gemini-embedding-001",
    embed_batch_size: int = 5,
) -> pd.DataFrame:
    if df.empty:
        return df

    logger.info(f"Starting semantic dedup on {len(df)} jobs")

    before = len(df)
    df = df.drop_duplicates(subset=["url"], keep="first").reset_index(drop=True)
    logger.info(f"Exact dedup: {before} -> {len(df)} ({before - len(df)} removed)")

    if len(df) < 2:
        return df

    jobs = df.to_dict("records")
    fingerprints = [make_fingerprint(j) for j in jobs]

    cache = load_embed_cache(embed_cache_path)
    to_embed = []

    for i, fp in enumerate(fingerprints):
        if fp not in cache:
            to_embed.append(fp)

    logger.info(
        f"Embeddings: {len(fingerprints) - len(to_embed)} cached, "
        f"{len(to_embed)} new to embed"
    )

    if to_embed:
        total_batches = (len(to_embed) + embed_batch_size - 1) // embed_batch_size
        success_count = 0

        for start in range(0, len(to_embed), embed_batch_size):
            batch_num = start // embed_batch_size + 1
            batch = to_embed[start : start + embed_batch_size]

            try:
                batch_embeds = embed_with_retry(batch, google_api_key, embed_model)
                for fp, emb in zip(batch, batch_embeds):
                    cache[fp] = emb
                success_count += len(batch)
            except Exception as e:
                logger.error(f"Batch {batch_num} failed after retries: {e}")

            # Save cache every 10 batches (crash-safe)
            if batch_num % 10 == 0:
                save_embed_cache(cache, embed_cache_path)
                logger.info(f"Embedded {success_count}/{len(to_embed)} ({batch_num}/{total_batches} batches)")

            time.sleep(5)

        # Final save
        save_embed_cache(cache, embed_cache_path)
        logger.info(f"Embedding complete: {success_count}/{len(to_embed)} succeeded")

    embeddings = []
    valid_indices = []
    for i, fp in enumerate(fingerprints):
        emb = cache.get(fp)
        if emb is not None:
            embeddings.append(emb)
            valid_indices.append(i)

    if len(embeddings) < 2:
        logger.warning("Not enough embeddings for similarity check")
        return df

    emb_matrix = np.array(embeddings)
    norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = emb_matrix / norms
    sim_matrix = normed @ normed.T

    drop_indices = set()
    n = len(valid_indices)

    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= similarity_threshold:
                idx_a = valid_indices[i]
                idx_b = valid_indices[j]

                if idx_a in drop_indices or idx_b in drop_indices:
                    continue

                desc_a = str(jobs[idx_a].get("full_description", ""))
                desc_b = str(jobs[idx_b].get("full_description", ""))

                if jaccard_tokens(desc_a, desc_b) >= description_overlap:
                    keep, drop = pick_richer_job(jobs[idx_a], jobs[idx_b])
                    drop_idx = idx_a if drop is jobs[idx_a] else idx_b
                    drop_indices.add(drop_idx)

    keep = [i for i in range(len(df)) if i not in drop_indices]
    result = df.iloc[keep].reset_index(drop=True)
    logger.info(
        f"Semantic dedup: {len(df)} -> {len(result)} "
        f"({len(drop_indices)} semantic duplicates removed)"
    )
    return result