"""
Embedding Cache — Redis with In-Memory Fallback.

Caches SentenceTransformer embeddings to avoid recomputing the same
vectors repeatedly. Uses Redis if available, otherwise falls back
to a Python dictionary (works locally without any setup).

Performance Impact:
    - Skills like "Python", "JavaScript", "AWS" appear thousands of times
      across candidates. Caching their embeddings saves ~95% of compute
      time when processing large batches.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """Thread-safe embedding cache with Redis + in-memory fallback."""

    def __init__(self) -> None:
        self._redis_client = None
        self._memory_cache: dict[str, list[float]] = {}
        self._hits = 0
        self._misses = 0

        # Try connecting to Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            import redis
            self._redis_client = redis.from_url(
                redis_url,
                socket_connect_timeout=2,
                decode_responses=True,
            )
            self._redis_client.ping()
            logger.info("EmbeddingCache: Connected to Redis at %s", redis_url)
        except Exception:
            self._redis_client = None
            logger.info(
                "EmbeddingCache: Redis not available. Using in-memory cache. "
                "(This is fine for local development)"
            )

    def get(self, key: str) -> Optional[list[float]]:
        """Retrieve a cached embedding vector.

        Args:
            key: The text string whose embedding was cached.

        Returns:
            The embedding vector as a list of floats, or None if not cached.
        """
        # Try Redis first
        if self._redis_client:
            try:
                val = self._redis_client.get(f"emb:{key}")
                if val:
                    self._hits += 1
                    return json.loads(val)
            except Exception:
                pass

        # Fallback to in-memory
        if key in self._memory_cache:
            self._hits += 1
            return self._memory_cache[key]

        self._misses += 1
        return None

    def set(self, key: str, embedding: list[float]) -> None:
        """Store an embedding vector in the cache.

        Args:
            key: The text string.
            embedding: The embedding vector.
        """
        # Store in Redis if available (with 24h TTL)
        if self._redis_client:
            try:
                self._redis_client.set(
                    f"emb:{key}",
                    json.dumps(embedding),
                    ex=86400,  # Expire after 24 hours
                )
            except Exception:
                pass

        # Always store in memory as a fast local fallback
        self._memory_cache[key] = embedding

    @property
    def stats(self) -> dict[str, int]:
        """Return cache hit/miss statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate_percent": round(hit_rate, 1),
            "memory_entries": len(self._memory_cache),
        }


# Global singleton instance
_cache_instance: Optional[EmbeddingCache] = None


def get_embedding_cache() -> EmbeddingCache:
    """Get or create the global EmbeddingCache singleton."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = EmbeddingCache()
    return _cache_instance
