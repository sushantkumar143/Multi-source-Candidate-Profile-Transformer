"""
Default pipeline settings.

Centralized constants and defaults used across all pipeline stages.
Changing these values affects the entire pipeline deterministically.
"""

from __future__ import annotations


class Settings:
    """Pipeline-wide settings and defaults."""

    # ── Source Reliability Scores ──
    # These scores reflect how trustworthy each source type is.
    # Used by the conflict resolver and confidence engine.
    SOURCE_RELIABILITY: dict[str, float] = {
        "csv": 0.80,       # Structured, but may be stale or manually entered
        "linkedin": 0.85,  # Self-reported but curated, generally accurate
        "github": 0.75,    # Public profile, objectively verifiable via repos
        "resume": 0.70,    # Unstructured, extraction may be imprecise
        "recruiter_notes": 0.50,  # Informal, subjective, potentially outdated
    }

    # Field-specific reliability matrix
    FIELD_SOURCE_RELIABILITY: dict[str, dict[str, float]] = {
        "full_name": {"csv": 0.90, "linkedin": 0.85, "resume": 0.70, "github": 0.60, "recruiter_notes": 0.50},
        "emails": {"csv": 0.95, "linkedin": 0.90, "resume": 0.85, "github": 0.90, "recruiter_notes": 0.50},
        "phones": {"csv": 0.95, "linkedin": 0.90, "resume": 0.85, "github": 0.60, "recruiter_notes": 0.50},
        "headline": {"linkedin": 0.85, "resume": 0.80, "csv": 0.70, "github": 0.60, "recruiter_notes": 0.50},
        "location": {"linkedin": 0.85, "resume": 0.80, "csv": 0.75, "github": 0.70, "recruiter_notes": 0.50},
        "links": {"github": 0.95, "linkedin": 0.90, "resume": 0.85, "csv": 0.80, "recruiter_notes": 0.50},
        "skills": {"github": 0.90, "linkedin": 0.85, "resume": 0.80, "csv": 0.70, "recruiter_notes": 0.50},
        "experience": {"resume": 0.85, "linkedin": 0.80, "csv": 0.60, "github": 0.40, "recruiter_notes": 0.50},
        "education": {"resume": 0.85, "linkedin": 0.80, "csv": 0.70, "github": 0.40, "recruiter_notes": 0.50},
    }

    # ── Conflict Resolution Weights ──
    CONFLICT_WEIGHT_SOURCE_RELIABILITY: float = 0.30
    CONFLICT_WEIGHT_AGREEMENT: float = 0.25
    CONFLICT_WEIGHT_EXTRACTION: float = 0.20
    CONFLICT_WEIGHT_FRESHNESS: float = 0.15
    CONFLICT_WEIGHT_PENALTY: float = 0.10

    # ── Confidence Engine Weights ──
    CONFIDENCE_WEIGHT_SOURCE: float = 0.30
    CONFIDENCE_WEIGHT_AGREEMENT: float = 0.30
    CONFIDENCE_WEIGHT_EXTRACTION: float = 0.20
    CONFIDENCE_WEIGHT_NORMALIZATION: float = 0.10
    CONFIDENCE_WEIGHT_CONFLICT: float = 0.10

    # ── Default Phone Country ──
    DEFAULT_PHONE_REGION: str = "IN"  # Default country for phone normalization

    # ── Skill Canonical Names ──
    # Map of common variations to canonical skill names
    SKILL_CANONICAL_MAP: dict[str, str] = {
        "python": "Python",
        "python3": "Python",
        "python 3": "Python",
        "py": "Python",
        "javascript": "JavaScript",
        "js": "JavaScript",
        "node.js": "Node.js",
        "nodejs": "Node.js",
        "node": "Node.js",
        "typescript": "TypeScript",
        "ts": "TypeScript",
        "react": "React",
        "reactjs": "React",
        "react.js": "React",
        "angular": "Angular",
        "angularjs": "Angular",
        "vue": "Vue.js",
        "vuejs": "Vue.js",
        "vue.js": "Vue.js",
        "java": "Java",
        "c++": "C++",
        "cpp": "C++",
        "c#": "C#",
        "csharp": "C#",
        "c sharp": "C#",
        "golang": "Go",
        "go": "Go",
        "rust": "Rust",
        "ruby": "Ruby",
        "swift": "Swift",
        "kotlin": "Kotlin",
        "scala": "Scala",
        "r": "R",
        "sql": "SQL",
        "mysql": "MySQL",
        "postgresql": "PostgreSQL",
        "postgres": "PostgreSQL",
        "mongodb": "MongoDB",
        "mongo": "MongoDB",
        "redis": "Redis",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "k8s": "Kubernetes",
        "aws": "AWS",
        "amazon web services": "AWS",
        "gcp": "GCP",
        "google cloud": "GCP",
        "google cloud platform": "GCP",
        "azure": "Azure",
        "microsoft azure": "Azure",
        "terraform": "Terraform",
        "ansible": "Ansible",
        "jenkins": "Jenkins",
        "git": "Git",
        "github": "GitHub",
        "ci/cd": "CI/CD",
        "cicd": "CI/CD",
        "machine learning": "Machine Learning",
        "ml": "Machine Learning",
        "deep learning": "Deep Learning",
        "dl": "Deep Learning",
        "natural language processing": "NLP",
        "nlp": "NLP",
        "computer vision": "Computer Vision",
        "cv": "Computer Vision",
        "tensorflow": "TensorFlow",
        "tf": "TensorFlow",
        "pytorch": "PyTorch",
        "torch": "PyTorch",
        "keras": "Keras",
        "scikit-learn": "scikit-learn",
        "sklearn": "scikit-learn",
        "pandas": "pandas",
        "numpy": "NumPy",
        "spark": "Apache Spark",
        "apache spark": "Apache Spark",
        "pyspark": "Apache Spark",
        "hadoop": "Hadoop",
        "kafka": "Apache Kafka",
        "apache kafka": "Apache Kafka",
        "airflow": "Apache Airflow",
        "apache airflow": "Apache Airflow",
        "flask": "Flask",
        "django": "Django",
        "fastapi": "FastAPI",
        "fast api": "FastAPI",
        "rest": "REST APIs",
        "rest api": "REST APIs",
        "rest apis": "REST APIs",
        "restful": "REST APIs",
        "graphql": "GraphQL",
        "html": "HTML",
        "css": "CSS",
        "linux": "Linux",
        "unix": "Linux",
        "agile": "Agile",
        "scrum": "Scrum",
        "data engineering": "Data Engineering",
        "data science": "Data Science",
        "data analysis": "Data Analysis",
        "etl": "ETL",
    }

    # ── File Discovery Patterns ──
    CSV_PATTERNS: list[str] = ["candidate.csv", "candidates.csv"]
    RESUME_PATTERNS: list[str] = ["resume.pdf", "resume.PDF"]
    GITHUB_PATTERNS: list[str] = ["github_profile.json", "github.json"]
    LINKEDIN_PATTERNS: list[str] = ["linkedin.txt", "linkedin_profile.txt"]
    RECRUITER_NOTES_PATTERNS: list[str] = ["recruiter_notes.txt", "notes.txt"]
    CONFIG_PATTERNS: list[str] = ["config.json"]
