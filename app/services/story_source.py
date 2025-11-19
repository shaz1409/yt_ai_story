"""Story Source Service - generates multiple story candidates for niches."""

import uuid
from typing import Any, Optional

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import StoryCandidate


# Niche-specific story templates for stub generation
NICHE_TEMPLATES = {
    "courtroom": [
        {
            "title": "Judge's Verdict Shocks Everyone in Courtroom",
            "template": "In a packed courtroom, the judge delivers a verdict that leaves everyone stunned. {context} The defendant's reaction is completely unexpected, causing chaos in the gallery.",
        },
        {
            "title": "Teen's Reaction to Sentence Goes Viral",
            "template": "A teenager stands before the judge, awaiting their sentence. {context} When the verdict is read, their response shocks the entire courtroom and quickly spreads online.",
        },
        {
            "title": "Judge Slams Defendant with Maximum Sentence",
            "template": "The judge looks down at the defendant with stern eyes. {context} After hearing the evidence, the judge delivers a sentence that sends a clear message to everyone present.",
        },
        {
            "title": "Courtroom Erupts After Unexpected Verdict",
            "template": "Tension fills the air as the jury returns. {context} When the verdict is announced, the courtroom explodes with reactions that no one saw coming.",
        },
        {
            "title": "Defendant's Laugh in Court Stuns Judge",
            "template": "The defendant sits calmly as the judge reads the charges. {context} But when the sentence is delivered, their unexpected laughter leaves the judge speechless.",
        },
    ],
    "relationship_drama": [
        {
            "title": "Wife Discovers Husband's Secret Life",
            "template": "She thought she knew everything about her husband. {context} But one day, she discovers a secret that changes everything and leaves her questioning their entire relationship.",
        },
        {
            "title": "Cheating Scandal Exposed at Family Dinner",
            "template": "The family gathers for what should be a happy dinner. {context} But when the truth comes out, the evening turns into a dramatic confrontation that tears the family apart.",
        },
        {
            "title": "Best Friend's Betrayal Revealed",
            "template": "They were inseparable for years, sharing everything. {context} But when the truth about their friendship is revealed, it becomes clear that trust was never what it seemed.",
        },
        {
            "title": "Ex Shows Up at Wedding with Shocking News",
            "template": "The wedding day arrives, everything seems perfect. {context} But when an ex-partner shows up with unexpected news, the ceremony becomes a scene of drama and heartbreak.",
        },
    ],
    "injustice": [
        {
            "title": "Worker Fired for Speaking Truth",
            "template": "They did the right thing, reported the problem. {context} But instead of being thanked, they were fired, leaving them to fight for justice against a system that failed them.",
        },
        {
            "title": "Student Expelled After False Accusation",
            "template": "A student's future hangs in the balance. {context} Despite being innocent, they face expulsion based on lies, forcing them to fight for their reputation and future.",
        },
        {
            "title": "Family Loses Everything Due to Corporate Greed",
            "template": "They worked hard, saved everything. {context} But when a corporation's actions destroy their livelihood, they're left with nothing and must fight for what's right.",
        },
    ],
    "workplace_drama": [
        {
            "title": "Boss Fires Employee for Refusing Unethical Task",
            "template": "They were asked to do something wrong. {context} When they refused, their boss fired them on the spot, creating a workplace drama that exposes the company's true values.",
        },
        {
            "title": "Coworker Steals Credit for Major Project",
            "template": "They spent months working on the project. {context} But when it succeeds, a coworker takes all the credit, leaving them to fight for recognition they deserve.",
        },
    ],
}


class StorySourceService:
    """Generates multiple story candidates for given niches or topics."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the story source service.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger

    def generate_candidates_from_topic(
        self, topic: str, niche: str = "courtroom", num_candidates: int = 5
    ) -> list[StoryCandidate]:
        """
        Generate multiple raw story candidates based on a topic and niche.

        Args:
            topic: Specific topic to base stories on
            niche: Story niche (courtroom, relationship_drama, etc.)
            num_candidates: Number of candidates to generate

        Returns:
            List of StoryCandidate objects
        """
        self.logger.info(f"Generating {num_candidates} candidates from topic: '{topic}' (niche: {niche})")

        # Check if we should use LLM
        use_llm = getattr(self.settings, "use_llm_for_story_finder", False) and self.settings.openai_api_key

        if use_llm:
            candidates = self._generate_candidates_llm(topic, niche, num_candidates)
        else:
            candidates = self._generate_candidates_stub(topic, niche, num_candidates)

        self.logger.info(f"Generated {len(candidates)} candidates from topic")
        return candidates

    def generate_candidates_for_niche(self, niche: str = "courtroom", num_candidates: int = 5) -> list[StoryCandidate]:
        """
        Generate candidates for a niche without a specific topic.

        Args:
            niche: Story niche (courtroom, relationship_drama, injustice, etc.)
            num_candidates: Number of candidates to generate

        Returns:
            List of StoryCandidate objects
        """
        self.logger.info(f"Generating {num_candidates} candidates for niche: {niche}")

        # Check if we should use LLM
        use_llm = getattr(self.settings, "use_llm_for_story_finder", False) and self.settings.openai_api_key

        if use_llm:
            candidates = self._generate_candidates_llm(None, niche, num_candidates)
        else:
            candidates = self._generate_candidates_stub(None, niche, num_candidates)

        self.logger.info(f"Generated {len(candidates)} candidates for niche: {niche}")
        return candidates

    def _generate_candidates_stub(
        self, topic: Optional[str], niche: str, num_candidates: int
    ) -> list[StoryCandidate]:
        """Generate candidates using stub templates."""
        templates = NICHE_TEMPLATES.get(niche, NICHE_TEMPLATES["courtroom"])
        candidates = []

        for i in range(num_candidates):
            template = templates[i % len(templates)]
            candidate_id = f"candidate_{uuid.uuid4().hex[:12]}"

            # Fill template with topic context if provided
            context = f"Related to {topic}" if topic else "In a dramatic turn of events"
            raw_text = template["template"].format(context=context)

            # If topic provided, enhance the text
            if topic:
                raw_text = f"{raw_text} The story involves {topic.lower()}, creating a narrative that captures attention."

            candidate = StoryCandidate(
                id=candidate_id,
                source_id=candidate_id,  # For backward compatibility
                title=template["title"],
                raw_text=raw_text,
                source=f"stub_{niche}",
                niche=niche,
                source_type="stub",
                metadata={"generation_method": "stub", "niche": niche},
            )

            candidates.append(candidate)

        return candidates

    def _generate_candidates_llm(
        self, topic: Optional[str], niche: str, num_candidates: int
    ) -> list[StoryCandidate]:
        """Generate candidates using LLM."""
        try:
            from openai import OpenAI
        except ImportError:
            self.logger.warning("OpenAI not available, falling back to stub")
            return self._generate_candidates_stub(topic, niche, num_candidates)

        if not self.settings.openai_api_key:
            self.logger.warning("OpenAI API key not set, falling back to stub")
            return self._generate_candidates_stub(topic, niche, num_candidates)

        client = OpenAI(api_key=self.settings.openai_api_key)

        self.logger.info(f"Using LLM to generate {num_candidates} candidates for niche: {niche}")

        prompt = f"""Generate {num_candidates} short, dramatic story ideas for {niche} content.

Each story should be:
- 100-200 words
- High emotional impact (rage, shock, injustice)
- Clear narrative with a twist
- Suitable for 45-60 second YouTube Shorts

{"Focus on stories related to: " + topic if topic else "Generate diverse stories in the " + niche + " niche"}

Return as a JSON array with this structure:
[
  {{
    "title": "Story title",
    "raw_text": "Full story text (100-200 words)"
  }},
  ...
]
"""

        try:
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at creating viral, emotional story content for YouTube Shorts. Generate dramatic, engaging stories with strong emotional hooks.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.9,
            )

            import json

            content = response.choices[0].message.content
            data = json.loads(content)

            # Extract stories (handle both array and object with "stories" key)
            stories = data.get("stories", []) if isinstance(data, dict) else data

            candidates = []
            for i, story in enumerate(stories[:num_candidates]):
                candidate_id = f"candidate_{uuid.uuid4().hex[:12]}"
                candidate = StoryCandidate(
                    id=candidate_id,
                    source_id=candidate_id,
                    title=story.get("title", f"Story {i+1}"),
                    raw_text=story.get("raw_text", ""),
                    source=f"llm_{niche}",
                    niche=niche,
                    source_type="llm_generated",
                    metadata={"generation_method": "llm", "niche": niche, "topic": topic},
                )
                candidates.append(candidate)

            return candidates

        except Exception as e:
            self.logger.error(f"LLM generation failed: {e}, falling back to stub")
            return self._generate_candidates_stub(topic, niche, num_candidates)

