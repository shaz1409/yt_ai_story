"""Virality Scoring Engine - scores story candidates for emotional virality."""

import re
from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import StoryCandidate, ViralityScore


class ViralityScorer:
    """Scores story candidates on multiple virality dimensions."""

    # Scoring weights
    WEIGHTS = {
        "shock": 0.30,
        "rage": 0.25,
        "injustice": 0.20,
        "relatability": 0.10,
        "twist_strength": 0.10,
        "clarity": 0.05,
    }

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the virality scorer.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.use_llm_scoring = getattr(settings, "use_llm_for_story_finder", False) and settings.openai_api_key

    def score_candidate(self, candidate: StoryCandidate) -> ViralityScore:
        """
        Compute a detailed virality score for a single candidate.

        Args:
            candidate: Story candidate to score

        Returns:
            ViralityScore with all dimensions
        """
        self.logger.debug(f"Scoring candidate: {candidate.id} - {candidate.title}")

        if self.use_llm_scoring:
            score = self._score_with_llm(candidate)
        else:
            score = self._score_with_heuristics(candidate)

        # Calculate overall score
        score.overall_score = self._calculate_overall_score(score)

        self.logger.debug(
            f"Candidate {candidate.id} scored: {score.overall_score:.3f} "
            f"(shock={score.shock:.2f}, rage={score.rage:.2f}, injustice={score.injustice:.2f})"
        )

        return score

    def rank_candidates(
        self, candidates: list[StoryCandidate]
    ) -> list[tuple[StoryCandidate, ViralityScore]]:
        """
        Score and return candidates sorted by overall_score (descending).

        Args:
            candidates: List of story candidates

        Returns:
            List of (candidate, score) tuples sorted by overall_score descending
        """
        self.logger.info(f"Ranking {len(candidates)} candidates by virality")

        scored = [(candidate, self.score_candidate(candidate)) for candidate in candidates]

        # Sort by overall_score descending
        scored.sort(key=lambda x: x[1].overall_score, reverse=True)

        # Log top 3
        self.logger.info("Top 3 candidates by virality:")
        for i, (candidate, score) in enumerate(scored[:3], 1):
            self.logger.info(
                f"  {i}. {candidate.title[:50]}... "
                f"(score: {score.overall_score:.3f}, shock={score.shock:.2f}, rage={score.rage:.2f})"
            )

        return scored

    def _score_with_heuristics(self, candidate: StoryCandidate) -> ViralityScore:
        """Score candidate using keyword-based heuristics."""
        text_lower = candidate.raw_text.lower()
        title_lower = candidate.title.lower()
        combined_text = f"{title_lower} {text_lower}"

        # Shock score - unexpected, surprising events
        shock_keywords = [
            "shocking",
            "unexpected",
            "stunned",
            "explodes",
            "erupts",
            "suddenly",
            "out of nowhere",
            "never saw coming",
        ]
        shock_count = sum(1 for keyword in shock_keywords if keyword in combined_text)
        shock = min(0.3 + (shock_count * 0.15), 1.0)

        # Rage score - triggers anger/indignation
        rage_keywords = [
            "slams",
            "destroys",
            "crushes",
            "outrage",
            "infuriating",
            "disgusting",
            "unacceptable",
            "appalling",
            "betrayal",
            "cheating",
        ]
        rage_count = sum(1 for keyword in rage_keywords if keyword in combined_text)
        rage = min(0.2 + (rage_count * 0.2), 1.0)

        # Injustice score - unfair treatment
        injustice_keywords = [
            "unfair",
            "wrong",
            "innocent",
            "fired",
            "expelled",
            "lied",
            "stole",
            "betrayed",
            "abandoned",
            "discriminated",
        ]
        injustice_count = sum(1 for keyword in injustice_keywords if keyword in combined_text)
        injustice = min(0.25 + (injustice_count * 0.15), 1.0)

        # Relatability score - common situations
        relatable_keywords = [
            "boss",
            "coworker",
            "husband",
            "wife",
            "friend",
            "family",
            "work",
            "school",
            "relationship",
            "cheating",
            "fired",
        ]
        relatable_count = sum(1 for keyword in relatable_keywords if keyword in combined_text)
        relatability = min(0.3 + (relatable_count * 0.1), 1.0)

        # Twist strength - reversal, reveal
        twist_keywords = [
            "but",
            "however",
            "reveals",
            "discovers",
            "turns out",
            "actually",
            "truth",
            "secret",
            "lied",
            "wasn't",
        ]
        twist_count = sum(1 for keyword in twist_keywords if keyword in combined_text)
        twist_strength = min(0.2 + (twist_count * 0.15), 1.0)

        # Clarity - story structure and readability
        sentence_count = len(re.split(r"[.!?]+", candidate.raw_text))
        word_count = len(candidate.raw_text.split())
        # Optimal: 5-15 sentences, 100-300 words
        if 5 <= sentence_count <= 15 and 100 <= word_count <= 300:
            clarity = 0.9
        elif 3 <= sentence_count <= 20 and 50 <= word_count <= 500:
            clarity = 0.7
        else:
            clarity = 0.5

        return ViralityScore(
            candidate_id=candidate.id,
            overall_score=0.0,  # Will be calculated
            shock=shock,
            rage=rage,
            injustice=injustice,
            relatability=relatability,
            twist_strength=twist_strength,
            clarity=clarity,
        )

    def _score_with_llm(self, candidate: StoryCandidate) -> ViralityScore:
        """Score candidate using LLM analysis."""
        try:
            from openai import OpenAI
        except ImportError:
            self.logger.warning("OpenAI not available, falling back to heuristics")
            return self._score_with_heuristics(candidate)

        if not self.settings.openai_api_key:
            self.logger.warning("OpenAI API key not set, falling back to heuristics")
            return self._score_with_heuristics(candidate)

        client = OpenAI(api_key=self.settings.openai_api_key)

        prompt = f"""Analyze this story for virality potential and score each dimension (0.0-1.0):

Title: {candidate.title}
Story: {candidate.raw_text[:500]}

Score each dimension:
- shock: How surprising/unexpected (0.0-1.0)
- rage: How much it triggers anger/indignation (0.0-1.0)
- injustice: How unfair/unjust the situation is (0.0-1.0)
- relatability: How common/relatable the situation is (0.0-1.0)
- twist_strength: How strong the twist/reversal is (0.0-1.0)
- clarity: How easy the story is to follow (0.0-1.0)

Return ONLY valid JSON:
{{
  "shock": 0.0-1.0,
  "rage": 0.0-1.0,
  "injustice": 0.0-1.0,
  "relatability": 0.0-1.0,
  "twist_strength": 0.0-1.0,
  "clarity": 0.0-1.0
}}
"""

        try:
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing content for viral potential. Score stories objectively on emotional and engagement dimensions.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Lower temp for more consistent scoring
            )

            import json

            content = response.choices[0].message.content
            data = json.loads(content)

            return ViralityScore(
                candidate_id=candidate.id,
                overall_score=0.0,  # Will be calculated
                shock=float(data.get("shock", 0.5)),
                rage=float(data.get("rage", 0.5)),
                injustice=float(data.get("injustice", 0.5)),
                relatability=float(data.get("relatability", 0.5)),
                twist_strength=float(data.get("twist_strength", 0.5)),
                clarity=float(data.get("clarity", 0.5)),
            )

        except Exception as e:
            self.logger.error(f"LLM scoring failed: {e}, falling back to heuristics")
            return self._score_with_heuristics(candidate)

    def _calculate_overall_score(self, score: ViralityScore) -> float:
        """Calculate weighted overall score from dimension scores."""
        overall = (
            self.WEIGHTS["shock"] * score.shock
            + self.WEIGHTS["rage"] * score.rage
            + self.WEIGHTS["injustice"] * score.injustice
            + self.WEIGHTS["relatability"] * score.relatability
            + self.WEIGHTS["twist_strength"] * score.twist_strength
            + self.WEIGHTS["clarity"] * score.clarity
        )

        return min(max(overall, 0.0), 1.0)  # Clamp to 0.0-1.0

