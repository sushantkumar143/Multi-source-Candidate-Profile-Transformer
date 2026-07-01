"""
Semantic Matcher.

Computes semantic similarity between text fields (such as company names,
job titles, skills, etc.) using SentenceTransformer dense embeddings or
scikit-learn's TfidfVectorizer as a robust, fully offline fallback.
"""
import logging
import difflib
from typing import List
import numpy as np

logger = logging.getLogger(__name__)

# Try to load SentenceTransformers
SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    # We will try loading the model lazily to avoid startup delay
    _ST_MODEL = None
except ImportError:
    _ST_MODEL = None

# Lazy loading of ST model
def _get_st_model():
    global _ST_MODEL, SENTENCE_TRANSFORMERS_AVAILABLE
    if _ST_MODEL is not None:
        return _ST_MODEL
    try:
        # Load a tiny, fast model
        logger.info("Loading local SentenceTransformer model 'all-MiniLM-L6-v2'...")
        _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        SENTENCE_TRANSFORMERS_AVAILABLE = True
        return _ST_MODEL
    except Exception as e:
        logger.warning(
            f"Could not load SentenceTransformer (e.g. offline/network block): {e}. "
            "Falling back to local TF-IDF Cosine Similarity matcher."
        )
        # Prevent retries
        _ST_MODEL = False
        return None

def compute_st_similarity(text1: str, text2: str) -> float:
    """Compute cosine similarity using SentenceTransformer embeddings."""
    model = _get_st_model()
    if not model:
        return 0.0
    try:
        emb1, emb2 = model.encode([text1, text2])
        # Cosine similarity
        dot_product = np.dot(emb1, emb2)
        norm_a = np.linalg.norm(emb1)
        norm_b = np.linalg.norm(emb2)
        return float(dot_product / (norm_a * norm_b))
    except Exception as e:
        logger.warning(f"Error computing SentenceTransformer similarity: {e}")
        return 0.0

def compute_tfidf_similarity(text1: str, text2: str) -> float:
    """Compute char n-gram TF-IDF cosine similarity between two strings."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Use character 3-5 n-grams to capture spelling variations & prefixes
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
        vectors = vectorizer.fit_transform([text1, text2])
        sim = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
        return float(sim)
    except Exception as e:
        logger.warning(f"Error computing TF-IDF similarity: {e}")
        # Fallback to simple difflib SequenceMatcher
        return difflib.SequenceMatcher(None, text1, text2).ratio()

def are_semantically_equivalent(val1: str, val2: str, field_name: str = "") -> bool:
    """Determine if two strings are semantically equivalent."""
    if not val1 or not val2:
        return False
        
    s1, s2 = val1.strip().lower(), val2.strip().lower()
    if s1 == s2:
        return True
        
    # Check if one is a sub-phrase of the other (e.g. "Google LLC" vs "Google")
    if len(s1) > 3 and len(s2) > 3:
        if s1 in s2 or s2 in s1:
            return True
            
    # Try SentenceTransformers first
    sim = compute_st_similarity(s1, s2)
    if sim > 0.80:
        logger.debug(f"Semantic match found (ST): '{val1}' <=> '{val2}' (sim={sim:.2f})")
        return True
        
    # Fallback to local TF-IDF Char N-Gram similarity
    if sim == 0.0:
        sim = compute_tfidf_similarity(s1, s2)
        if sim > 0.75:
            logger.debug(f"Semantic match found (TF-IDF): '{val1}' <=> '{val2}' (sim={sim:.2f})")
            return True
            
    # Final backup: difflib SequenceMatcher ratio for short strings
    diff_ratio = difflib.SequenceMatcher(None, s1, s2).ratio()
    if diff_ratio > 0.85:
        logger.debug(f"Semantic match found (difflib): '{val1}' <=> '{val2}' (ratio={diff_ratio:.2f})")
        return True
        
    return False
