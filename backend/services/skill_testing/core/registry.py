from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SkillSemanticRegistry:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), lowercase=True)
        self._matrix = None
        self.name_to_id_map: dict[str, str] = {}
        self.capabilities_manifest = ""
        self._skills_cache: list[str] = []

    def build_index(self, tools_data: list[dict]):
        """Build a lightweight text index from tool names and descriptions."""
        if not tools_data:
            self._skills_cache = []
            self.name_to_id_map = {}
            self.capabilities_manifest = ""
            self._matrix = None
            return

        self._skills_cache = []
        self.name_to_id_map = {}
        summary_texts: list[str] = []
        lines = ["### SYSTEM AVAILABLE TOOLS AND CAPABILITIES ###"]

        for tool in tools_data:
            name = tool.get("name")
            skill_id = tool.get("skill_id") or tool.get("id")
            desc = tool.get("description", "")
            if not name or not skill_id:
                continue

            self.name_to_id_map[name] = skill_id
            self._skills_cache.append(name)
            summary_texts.append(f"{name} {desc}".strip())

            lines.append(f"- Tool Name: {name} (ID: {skill_id})")
            lines.append(f"  Description: {desc[:100]}...")

        self.capabilities_manifest = "\n".join(lines)
        self._matrix = self.vectorizer.fit_transform(summary_texts) if summary_texts else None
        print(
            f"✅ [REGISTRY] Đã nạp thành công và xây dựng chỉ mục text cho "
            f"{len(self._skills_cache)} kỹ năng."
        )

    def search(self, query: str, top_k: int = 1) -> list[tuple[str, float]]:
        if self._matrix is None or not self._skills_cache:
            return []

        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self._matrix)[0]
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:top_k]
        return [
            (self._skills_cache[index], float(score))
            for index, score in ranked
            if score > 0
        ]

    def get_all_tools(self) -> list[str]:
        return self._skills_cache

    def get_id_by_name(self, name: str) -> Optional[str]:
        return self.name_to_id_map.get(name)


semantic_registry = SkillSemanticRegistry()
