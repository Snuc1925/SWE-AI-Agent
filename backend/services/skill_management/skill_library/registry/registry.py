"""SkillRegistry — loads all skills from a directory and provides TF-IDF search."""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..models.skill import Skill


class SkillRegistry:
    """
    Loads skill folders (each containing SKILL.md) and indexes them for search.

    Directory structure expected:
        skills/
        └── my-skill/
            ├── SKILL.md        ← required
            ├── scripts/        ← optional
            └── assets/         ← optional
    """

    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Skill] = {}
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._tfidf_matrix = None
        self._index_names: List[str] = []

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def load_all(self) -> int:
        """Scan skills_dir, parse every SKILL.md, and build the search index."""
        self.skills.clear()
        for md_path in sorted(self.skills_dir.rglob("SKILL.md")):
            try:
                skill = Skill.from_md_file(md_path)
                self.skills[skill.name] = skill
            except Exception as exc:
                print(f"[SkillRegistry] WARNING: skipping {md_path} → {exc}")
        self._build_tfidf_index()
        return len(self.skills)

    def load_from_markdowns(self, markdowns: List[str]) -> int:
        """Build the index from a list of markdown strings (e.g. from DB)."""
        self.skills.clear()
        for md in markdowns:
            try:
                skill = Skill.from_markdown(md)
                self.skills[skill.name] = skill
            except Exception as exc:
                print(f"[SkillRegistry] WARNING: skipping markdown → {exc}")
        self._build_tfidf_index()
        return len(self.skills)

    def _build_tfidf_index(self) -> None:
        if not self.skills:
            return
        self._index_names = list(self.skills.keys())
        corpus = []
        for name in self._index_names:
            s = self.skills[name]
            text = (
                f"{s.name.replace('-', ' ')} "
                f"{s.description} "
                f"{' '.join(s.tags)} "
                f"{s.category.replace('/', ' ')}"
            )
            corpus.append(text.lower())
        self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self._tfidf_matrix = self._vectorizer.fit_transform(corpus)

    # ------------------------------------------------------------------ #
    # Search  (Epic 3)
    # ------------------------------------------------------------------ #
    def search(self, query: str, top_k: int = 3) -> List[Tuple[Skill, float]]:
        """Return top-k (Skill, score) tuples matching the query."""
        if self._vectorizer is None or not self.skills:
            return []
        q_vec = self._vectorizer.transform([query.lower()])
        scores = cosine_similarity(q_vec, self._tfidf_matrix).flatten()
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [
            (self.skills[self._index_names[i]], float(scores[i]))
            for i in top_idx
            if scores[i] > 0
        ]

    # ------------------------------------------------------------------ #
    # Accessors
    # ------------------------------------------------------------------ #
    def get(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    def all_skills(self) -> List[Skill]:
        return list(self.skills.values())

    def list_by_category(self, category_prefix: str) -> List[Skill]:
        return [s for s in self.skills.values() if s.category.startswith(category_prefix)]

    def __len__(self) -> int:
        return len(self.skills)
