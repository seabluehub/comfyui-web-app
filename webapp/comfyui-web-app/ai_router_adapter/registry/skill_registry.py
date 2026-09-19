"""
Skill Registry: Catalogs domain knowledge modules and specialized workflow guidelines.
"""
from typing import Dict, List, Optional
from ..schemas import SkillProfile


class SkillRegistry:
    """Manages domain skills that can be dynamically loaded into an agent."""

    def __init__(self):
        self._skills: Dict[str, SkillProfile] = {}
        self._register_default_skills()

    def _register_default_skills(self):
        defaults = [
            SkillProfile(
                skill_id="skill_code_audit",
                name="Code Architecture & Security Audit",
                description="Expertise in static code analysis, concurrency issues, memory leaks, and architectural refactoring.",
                tags=["coding", "audit", "security", "concurrency", "refactor", "bug"],
                system_prompt_template="""### [Skill Activated: Code Architecture & Security Audit]
- Conduct rigorous static analysis on provided code/diffs.
- Identify edge-case failures, thread-safety/concurrency race conditions, memory leaks, and anti-patterns.
- Always provide line-specific actionable fixes and refactored snippets with Big-O complexity notes.
"""
            ),
            SkillProfile(
                skill_id="skill_algorithm_reasoning",
                name="Algorithmic Proof & Complexity Reasoning",
                description="Specialized in formal algorithmic correctness proof, asymptotic complexity analysis, and mathematical logic.",
                tags=["reasoning", "algorithm", "math", "complexity", "logic", "proof"],
                system_prompt_template="""### [Skill Activated: Algorithmic Proof & Complexity Reasoning]
- Step-by-step rigorous logical deduction.
- Verify time complexity O(...) and space complexity O(...) with worst/average/best case bounds.
- Provide mathematical invariant checks and counter-example exploration before concluding.
"""
            ),
            SkillProfile(
                skill_id="skill_deep_research",
                name="Deep Information Synthesis & Fact Checking",
                description="Expertise in synthesizing search queries, cross-referencing multi-source findings, and eliminating misinformation.",
                tags=["search", "research", "information", "factcheck", "sources"],
                system_prompt_template="""### [Skill Activated: Deep Information Synthesis & Fact Checking]
- Collate raw data retrieved from tools, checking consistency across timestamps and sources.
- Highlight definitive facts vs. speculative claims with citation tags.
- Synthesize findings into structured bullet points with high informational density.
"""
            ),
            SkillProfile(
                skill_id="skill_executive_summary",
                name="Executive Strategic Synthesis",
                description="High-level summarization, trade-off matrix, risk assessment, and decision recommendation.",
                tags=["summary", "synthesis", "strategy", "decision", "report"],
                system_prompt_template="""### [Skill Activated: Executive Strategic Synthesis]
- Deliver structured conclusions: Executive Summary -> Detailed Findings -> Risk Matrix -> Actionable Roadmap.
- Be concise, objective, and highlight key trade-offs with explicit priority rankings.
"""
            ),
        ]
        for s in defaults:
            self.register(s)

    def register(self, profile: SkillProfile):
        self._skills[profile.skill_id] = profile

    def get(self, skill_id: str) -> Optional[SkillProfile]:
        return self._skills.get(skill_id)

    def list_all(self) -> List[SkillProfile]:
        return list(self._skills.values())
