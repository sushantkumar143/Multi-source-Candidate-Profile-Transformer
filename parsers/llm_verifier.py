"""
LLM Verification Layer

Uses Groq API with multi-key fallback to verify and correct parsed resume fields.
Acts as a strict verifier, avoiding hallucinations.
"""
import json
import logging
from typing import Any, Dict
import time
import os

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

logger = logging.getLogger(__name__)

# User provided keys for fallback
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1", ""),
    os.getenv("GROQ_API_KEY_2", ""),
    os.getenv("GROQ_API_KEY_3", "")
]
MODELS = ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]

def verify_profile(raw_text: str, parsed_json: Dict[str, Any]) -> Dict[str, Any]:
    """Verify and correct the parsed JSON using Groq LLM."""
    if not GROQ_AVAILABLE:
        logger.warning("Groq not installed. Skipping LLM verification.")
        return parsed_json
        
    prompt = f"""You are a strict Resume Verifier.
I have parsed a candidate's resume into JSON using a deterministic parser, but it may have errors or missing fields.
Below is the RAW RESUME TEXT followed by the PARSED JSON.

Your instructions:
1. Verify each field in the PARSED JSON against the RAW RESUME TEXT.
2. Correct any incorrect fields based ONLY on what is explicitly written in the raw text.
3. Fill missing fields ONLY if they are clearly inferable from the raw text.
4. DO NOT hallucinate. If a value cannot be verified, leave it as is or null.
5. Return ONLY valid JSON in the exact same structure as the PARSED JSON. Do not include markdown formatting or explanations.
6. CRITICAL: DO NOT include or add academic projects, personal projects, or course projects into the 'experience' section. The 'experience' section must only contain actual professional work history, jobs, internships, or professional training. Exclude projects entirely from the 'experience' list.

RAW RESUME TEXT:
{raw_text}

PARSED JSON:
{json.dumps(parsed_json, indent=2)}
"""

    for api_key in GROQ_KEYS:
        for model in MODELS:
            try:
                client = Groq(api_key=api_key)
                logger.info(f"Attempting LLM verification using Groq model {model}...")
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=4000,
                    timeout=10.0,
                )
                
                result_text = response.choices[0].message.content.strip()
                # Remove markdown code blocks if the model included them despite instructions
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                    
                verified_json = json.loads(result_text.strip())
                logger.info("LLM verification successful.")
                return verified_json
                
            except json.JSONDecodeError:
                logger.warning(f"Groq {model} returned invalid JSON. Falling back...")
            except Exception as e:
                logger.warning(f"Groq API error with {model}: {e}. Falling back...")
                
    logger.error("All Groq API fallbacks failed. Returning original parsed JSON.")
    return parsed_json
