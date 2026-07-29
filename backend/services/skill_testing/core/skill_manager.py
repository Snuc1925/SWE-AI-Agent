from typing import List

class SkillManager:
    @staticmethod
    def get_capabilities(skills: List[str]) -> str:
        if not skills or len(skills) == 0:
            return "No skills available. Please check the skill management service."
            
        categories = {}
        for skill_name in skills:
            skill_name_lower = skill_name.lower()
            if "java" in skill_name_lower:
                cat = "JAVA_DEVELOPMENT"
            elif "test" in skill_name_lower or "maven" in skill_name_lower or "pytest" in skill_name_lower:
                cat = "TESTING_&_VERIFICATION"
            elif "git" in skill_name_lower or "commit" in skill_name_lower:
                cat = "VERSION_CONTROL"
            else:
                cat = "GENERAL_UTILITIES"

            if cat not in categories:
                categories[cat] = []
                
            readable_desc = skill_name.replace("_", " ").capitalize()
            categories[cat].append(f"- {skill_name}: Capability to execute {readable_desc}")

        lines = ["### SYSTEM CAPABILITIES AND CATEGORIES ###"]
        for cat, skill_list in categories.items():
            lines.append(f"\n[{cat.upper()}]")
            lines.extend(skill_list)
            
        return "\n".join(lines)