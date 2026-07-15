"""AI-powered personalized health tips service (US-15, FR-E1, FR-E6).

Generates post-check-in personalized tips using AWS Bedrock (Claude) grounded in
SHS-approved content. All model calls are server-side; no PHI is sent.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.challenge import Task

logger = logging.getLogger(__name__)


class PersonalizedTip:
    """A personalized health tip with resource and next step."""

    def __init__(self, tip: str, resource: str, next_step: str):
        self.tip = tip
        self.resource = resource
        self.next_step = next_step

    def to_dict(self) -> dict:
        return {
            "tip": self.tip,
            "resource": self.resource,
            "next_step": self.next_step,
        }


class AITipsService:
    """Service for generating personalized health tips via AWS Bedrock (US-15)."""

    def __init__(self, config):
        """Initialize the AI tips service with configuration.

        Args:
            config: Settings object with AWS Bedrock configuration
        """
        self.config = config
        self.bedrock_client = None

        # Only initialize Bedrock client if tips are enabled
        if config.ai_tips_enabled:
            try:
                import boto3

                self.bedrock_client = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=config.aws_region,
                )
                logger.info(
                    f"Initialized Bedrock client in region {config.aws_region}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Bedrock client: {e}. "
                    "AI tips will use fallback content."
                )
                self.bedrock_client = None

    def generate_tip(
        self,
        task: Task,
        remaining_required_tasks: int,
        completed_count: int,
        total_count: int,
    ) -> PersonalizedTip:
        """Generate a personalized tip for a completed task (US-15, FR-E1).

        The tip is grounded in SHS-approved content and personalized by:
        - The specific task completed (e.g., vision check, nutrition workshop)
        - Student's remaining progress
        - Content tags associated with the task

        No PHI is sent to the model (FR-E6).

        Args:
            task: The task just completed
            remaining_required_tasks: Number of required tasks remaining
            completed_count: Total tasks completed so far
            total_count: Total tasks in the challenge

        Returns:
            PersonalizedTip with tip, resource, and next_step
        """
        # If Bedrock is not available, return a fallback tip
        if not self.config.ai_tips_enabled or self.bedrock_client is None:
            return self._generate_fallback_tip(
                task, remaining_required_tasks, completed_count, total_count
            )

        try:
            # Build the prompt with grounded content (no PHI)
            prompt = self._build_tip_prompt(
                task, remaining_required_tasks, completed_count, total_count
            )

            # Call AWS Bedrock with Claude
            response = self._call_bedrock(prompt)

            # Parse the response
            return self._parse_tip_response(response)

        except Exception as e:
            logger.error(f"Error generating AI tip: {e}", exc_info=True)
            # Fall back to static content on error
            return self._generate_fallback_tip(
                task, remaining_required_tasks, completed_count, total_count
            )

    def _build_tip_prompt(
        self,
        task: Task,
        remaining_required_tasks: int,
        completed_count: int,
        total_count: int,
    ) -> str:
        """Build the prompt for Claude (US-15, FR-E6).

        The prompt is constructed to:
        1. Ground responses in SHS-approved content
        2. Personalize by task and progress
        3. Not include any PHI (no student identifiers)
        """
        progress_context = (
            f"The student has completed {completed_count} of {total_count} tasks."
        )

        if remaining_required_tasks > 0:
            progress_context += (
                f" They have {remaining_required_tasks} required tasks remaining "
                f"to become prize-eligible."
            )
        else:
            progress_context += " They have completed all required tasks and are prize-eligible!"

        prompt = f"""You are a wellness educator for CSUB Student Health Services. A student just completed a wellness activity and needs a personalized health tip.

TASK COMPLETED: {task.title}
ACTIVITY TYPE: {task.activity_type}
TASK DESCRIPTION: {task.caption or "No description"}
CONTENT TAGS: {task.content_tags or "general wellness"}

STUDENT PROGRESS: {progress_context}

SHS-APPROVED WELLNESS CONTENT:
{self.config.shs_content_corpus}

Generate a personalized tip that:
1. Is directly relevant to the task they just completed
2. Acknowledges their progress toward completing the challenge
3. Is grounded in the SHS-approved content above
4. Includes a practical resource or action they can take
5. Suggests a meaningful next step

Respond in JSON format with exactly these fields:
{{
  "tip": "A 2-3 sentence personalized health tip relevant to the task",
  "resource": "A specific campus resource, service, or helpful link",
  "next_step": "An actionable next step the student can take"
}}

Keep the tone supportive, informative, and student-friendly. Do not include any medical advice or diagnosis."""

        return prompt

    def _call_bedrock(self, prompt: str) -> dict:
        """Call AWS Bedrock with the Claude model (FR-E6).

        Args:
            prompt: The constructed prompt with grounded content

        Returns:
            Parsed response from Claude
        """
        # Prepare the request body for Claude 3.5
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.config.bedrock_max_tokens,
            "temperature": self.config.bedrock_temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        # Call Bedrock
        response = self.bedrock_client.invoke_model(
            modelId=self.config.bedrock_model_id,
            body=json.dumps(request_body),
        )

        # Parse the response
        response_body = json.loads(response["body"].read())

        # Extract the text content from Claude's response
        content = response_body.get("content", [])
        if content and len(content) > 0:
            return {"text": content[0].get("text", "")}

        raise ValueError("Empty response from Bedrock")

    def _parse_tip_response(self, response: dict) -> PersonalizedTip:
        """Parse Claude's JSON response into a PersonalizedTip.

        Args:
            response: Response from Bedrock

        Returns:
            PersonalizedTip object
        """
        text = response.get("text", "")

        # Try to parse as JSON
        try:
            # Extract JSON from the response (might be wrapped in markdown)
            if "```json" in text:
                json_start = text.find("```json") + 7
                json_end = text.find("```", json_start)
                text = text[json_start:json_end].strip()
            elif "```" in text:
                json_start = text.find("```") + 3
                json_end = text.find("```", json_start)
                text = text[json_start:json_end].strip()

            data = json.loads(text)

            return PersonalizedTip(
                tip=data.get("tip", "Great job completing this wellness activity!"),
                resource=data.get(
                    "resource", "Visit Student Health Services for more information."
                ),
                next_step=data.get(
                    "next_step", "Continue with your next wellness task!"
                ),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            # Return a generic fallback
            return PersonalizedTip(
                tip="Great job completing this wellness activity! Keep up the healthy habits.",
                resource="Visit Student Health Services for personalized wellness support.",
                next_step="Check your passport to see what's next in your wellness journey!",
            )

    def _generate_fallback_tip(
        self,
        task: Task,
        remaining_required_tasks: int,
        completed_count: int,
        total_count: int,
    ) -> PersonalizedTip:
        """Generate a fallback tip when Bedrock is unavailable (US-15).

        These are static but still grounded in SHS content and personalized
        by task type and progress.
        """
        # Map activity types and content tags to fallback tips
        activity_tips = {
            "vision": PersonalizedTip(
                tip="Excellent work prioritizing your vision health! Remember to follow the 20-20-20 rule: every 20 minutes, look at something 20 feet away for 20 seconds to reduce eye strain from screens.",
                resource="Campus Health Services offers vision screening appointments. Call (661) 654-3277 to schedule.",
                next_step="Consider getting an annual eye exam, especially if you use screens frequently for classes.",
            ),
            "nutrition": PersonalizedTip(
                tip="Great choice focusing on nutrition! A balanced diet with proteins, whole grains, fruits, and vegetables fuels both your body and mind for academic success.",
                resource="Campus dining offers 'Balanced U' meal options. Look for the labels in the dining hall.",
                next_step="Challenge yourself to try one new healthy recipe or campus dining option this week.",
            ),
            "physical": PersonalizedTip(
                tip="Awesome job staying active! Regular physical activity improves mood, energy, and focus. Aim for 150 minutes of moderate exercise weekly.",
                resource="Campus Recreation Center offers free fitness classes for students. Check the schedule at the Rec Center.",
                next_step="Find a workout buddy or join a group fitness class to make exercise more fun and sustainable.",
            ),
            "mental": PersonalizedTip(
                tip="Thank you for prioritizing your mental wellness! Stress is normal, but taking proactive steps to manage it makes a huge difference in your college experience.",
                resource="Campus Counseling offers free confidential support. Available 24/7 at (661) 654-3360.",
                next_step="Try a 5-minute mindfulness exercise today. Even short breaks for deep breathing can reduce stress.",
            ),
            "screening": PersonalizedTip(
                tip="Smart move completing this health screening! Preventive care helps detect potential issues early and keeps you healthy throughout the semester.",
                resource="Student Health Services offers free or low-cost preventive services. Visit the SHS front desk for more info.",
                next_step="Stay up to date with recommended vaccinations and annual wellness check-ups.",
            ),
        }

        # Try to match task content tags or activity type
        task_key = None
        if task.content_tags:
            for key in activity_tips:
                if key in task.content_tags.lower():
                    task_key = key
                    break

        if not task_key and task.activity_type:
            activity_lower = task.activity_type.lower()
            for key in activity_tips:
                if key in activity_lower:
                    task_key = key
                    break

        # Default to a generic tip
        if task_key and task_key in activity_tips:
            tip = activity_tips[task_key]
        else:
            tip = PersonalizedTip(
                tip=f"Congratulations on completing {task.title}! You're building healthy habits that will serve you throughout college and beyond.",
                resource="Visit Student Health Services for personalized wellness guidance and campus resources.",
                next_step="Check your passport to see your progress and plan your next wellness activity.",
            )

        # Add progress acknowledgment
        if remaining_required_tasks == 0:
            tip.tip += " You've completed all required tasks and are now prize-eligible!"
        elif remaining_required_tasks == 1:
            tip.tip += " Just one more required task to become prize-eligible!"
        elif remaining_required_tasks <= 3:
            tip.tip += (
                f" Only {remaining_required_tasks} required tasks left to go!"
            )

        return tip


def get_ai_tips_service() -> AITipsService:
    """Dependency factory for the AI tips service."""
    from app.config import get_settings

    return AITipsService(get_settings())
