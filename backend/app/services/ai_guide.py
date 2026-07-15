"""Conversational wellness guide service (US-16, FR-E2, FR-E6).

Themed in-app assistant that answers wellness questions grounded in SHS content,
nudges next tasks, and links campus resources. Built on AWS Bedrock (Claude).
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.challenge import Challenge, Task

logger = logging.getLogger(__name__)


class GuideResponse:
    """Response from the wellness guide."""

    def __init__(self, message: str, next_task_nudge: str | None = None):
        self.message = message
        self.next_task_nudge = next_task_nudge

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "next_task_nudge": self.next_task_nudge,
        }


class ConversationGuideService:
    """Themed wellness guide for answering student questions (US-16)."""

    def __init__(self, config):
        """Initialize the conversation guide service.

        Args:
            config: Settings object with AWS Bedrock and SHS content configuration
        """
        self.config = config
        self.bedrock_client = None

        # Initialize Bedrock client if enabled
        if config.conversation_guide_enabled:
            try:
                import boto3

                self.bedrock_client = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=config.aws_region,
                )
                logger.info(
                    f"Initialized Bedrock client for conversation guide in region {config.aws_region}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Bedrock client: {e}. "
                    "Conversation guide will use fallback responses."
                )
                self.bedrock_client = None

    def get_response(
        self,
        user_message: str,
        conversation_history: list[dict],
        theme_name: str | None,
        challenge: Challenge | None,
        next_available_tasks: list[Task],
        completed_task_count: int,
        total_task_count: int,
    ) -> GuideResponse:
        """Generate a response to a user's wellness question (US-16, FR-E2, FR-E6).

        The guide response is:
        1. Grounded in SHS-approved wellness content
        2. Themed according to the active challenge (e.g., "Stranger Things")
        3. Aware of the student's progress and next available tasks
        4. Links to relevant campus resources

        No PHI is sent to the model (FR-E6).

        Args:
            user_message: The student's question or message
            conversation_history: Recent conversation messages for context
            theme_name: The active challenge theme (e.g., "Stranger Things")
            challenge: The active Challenge object (optional)
            next_available_tasks: List of tasks the student hasn't completed
            completed_task_count: Number of tasks completed
            total_task_count: Total tasks in the challenge

        Returns:
            GuideResponse with themed message and optional task nudge
        """
        # If Bedrock is not available, return a fallback response
        if not self.config.conversation_guide_enabled or self.bedrock_client is None:
            return self._generate_fallback_response(
                user_message, theme_name, next_available_tasks
            )

        try:
            # Build the prompt with theme, grounded content, and context
            prompt = self._build_guide_prompt(
                user_message,
                conversation_history,
                theme_name,
                challenge,
                next_available_tasks,
                completed_task_count,
                total_task_count,
            )

            # Call AWS Bedrock with Claude
            response = self._call_bedrock(prompt, conversation_history)

            # Parse the response
            return self._parse_guide_response(response)

        except Exception as e:
            logger.error(f"Error generating guide response: {e}", exc_info=True)
            # Fall back to static content on error
            return self._generate_fallback_response(
                user_message, theme_name, next_available_tasks
            )

    def _build_guide_prompt(
        self,
        user_message: str,
        conversation_history: list[dict],
        theme_name: str | None,
        challenge: Challenge | None,
        next_available_tasks: list[Task],
        completed_task_count: int,
        total_task_count: int,
    ) -> str:
        """Build the system prompt for the themed wellness guide (US-16, FR-E2, FR-E6).

        The prompt establishes:
        1. The guide's themed persona (e.g., "Stranger Things" character)
        2. Grounding in SHS-approved wellness content
        3. Awareness of student progress and next tasks
        4. Links to campus resources
        5. Safety guardrails (covered in US-17, but foundation here)
        """
        # Get theme persona from configuration
        theme_persona = self.config.theme_personas.get(
            theme_name or "default", self.config.theme_personas["default"]
        )

        # Build progress context
        if challenge:
            progress_context = f"The student has completed {completed_task_count} of {total_task_count} tasks in the '{challenge.name}' challenge."
        else:
            progress_context = "The student is exploring wellness topics."

        # Build next task nudge context
        task_context = ""
        if next_available_tasks:
            task_context = "\n\nUPCOMING TASKS the student can complete:\n"
            for task in next_available_tasks[:3]:  # Show max 3 tasks
                task_context += f"- {task.title}: {task.caption or 'No description'} ({task.activity_type})\n"
            task_context += "\nYou can naturally mention relevant upcoming tasks when appropriate."

        system_prompt = f"""You are a wellness guide assistant for CSUB Student Health Services. {theme_persona}

STUDENT PROGRESS: {progress_context}{task_context}

SHS-APPROVED WELLNESS CONTENT (ground all responses in this content):
{self.config.shs_content_corpus}

YOUR ROLE:
1. Answer wellness questions clearly and supportively using only SHS-approved content above
2. When relevant, gently nudge the student toward their next available task
3. Link to specific campus resources (Student Health Services, Counseling, Recreation Center, etc.)
4. Stay in character with your themed persona but prioritize accurate health information
5. If a question is outside the SHS content scope, acknowledge limitations and refer to SHS professionals

CAMPUS RESOURCES to reference:
- Student Health Services: (661) 654-3277
- Campus Counseling (24/7 Crisis): (661) 654-3360
- Campus Recreation Center: Free fitness classes and facilities
- National Suicide Prevention Lifeline: 988
- Campus Police (emergency): (661) 654-2111

GUIDELINES:
- Keep responses concise (2-4 paragraphs)
- Be supportive and student-friendly
- Never provide medical diagnosis or advice beyond the SHS content
- Respect student privacy - don't ask for or reference personal health information
- If the student seems in crisis, immediately provide crisis resources

Respond naturally in conversation. Do not use special formatting or JSON unless specifically requested."""

        return system_prompt

    def _call_bedrock(
        self, system_prompt: str, conversation_history: list[dict]
    ) -> dict:
        """Call AWS Bedrock with Claude for conversation (FR-E6).

        Args:
            system_prompt: The system prompt with theme, content, and context
            conversation_history: Recent conversation messages

        Returns:
            Parsed response from Claude
        """
        # Prepare messages with conversation history
        messages = []

        # Add conversation history (limited by config)
        for msg in conversation_history[
            -self.config.max_conversation_history :
        ]:
            messages.append(
                {
                    "role": msg["role"],
                    "content": msg["content"],
                }
            )

        # Prepare the request body for Claude 3.5
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.config.bedrock_max_tokens,
            "temperature": self.config.bedrock_temperature,
            "system": system_prompt,
            "messages": messages,
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

    def _parse_guide_response(self, response: dict) -> GuideResponse:
        """Parse Claude's response into a GuideResponse.

        Args:
            response: Response from Bedrock

        Returns:
            GuideResponse object
        """
        text = response.get("text", "")

        # For now, return the full text as the message
        # In the future, could parse structured responses for task nudges
        return GuideResponse(message=text, next_task_nudge=None)

    def _generate_fallback_response(
        self,
        user_message: str,
        theme_name: str | None,
        next_available_tasks: list[Task],
    ) -> GuideResponse:
        """Generate a fallback response when Bedrock is unavailable (US-16).

        These are static but still helpful and grounded in SHS content.
        """
        # Default fallback based on keywords in the user message
        message_lower = user_message.lower()

        if any(
            word in message_lower for word in ["vision", "eye", "eyes", "screen"]
        ):
            response = (
                "Great question about vision health! If you're using screens frequently for classes, "
                "remember the 20-20-20 rule: Every 20 minutes, look at something 20 feet away for 20 seconds. "
                "This helps reduce eye strain. Campus Health Services also offers vision screening appointments. "
                "Call (661) 654-3277 to schedule."
            )
        elif any(
            word in message_lower
            for word in ["nutrition", "food", "eat", "meal", "diet"]
        ):
            response = (
                "Nutrition is so important for both your body and mind! A balanced diet with proteins, "
                "whole grains, fruits, and vegetables fuels your academic success. Campus dining offers "
                "'Balanced U' meal options - look for the labels in the dining hall. Don't forget to stay "
                "hydrated with 8 glasses of water daily."
            )
        elif any(
            word in message_lower
            for word in ["exercise", "workout", "fitness", "physical", "active"]
        ):
            response = (
                "Regular physical activity is fantastic for your health! Aim for 150 minutes of moderate "
                "exercise weekly. The Campus Recreation Center offers free fitness classes for students, "
                "and even walking between classes counts. Find activities you enjoy to make fitness sustainable."
            )
        elif any(
            word in message_lower
            for word in ["stress", "anxiety", "mental", "counseling", "worried"]
        ):
            response = (
                "Taking care of your mental health is just as important as physical health. Stress is normal, "
                "but chronic stress needs attention. Campus Counseling offers free confidential support - "
                "they're available 24/7 at (661) 654-3360. Even 5 minutes of deep breathing or mindfulness "
                "can help reduce stress."
            )
        elif any(word in message_lower for word in ["sleep", "tired", "rest"]):
            response = (
                "Sleep is crucial for your health and academic performance! Aim for 7-9 hours nightly and "
                "keep a consistent sleep schedule, even on weekends. Avoid screens 1 hour before bed and "
                "create a relaxing bedtime routine. Your body and mind will thank you."
            )
        else:
            response = (
                "Thanks for your question! For personalized wellness guidance, I recommend reaching out to "
                "Student Health Services at (661) 654-3277. They can provide expert support tailored to your needs. "
                "In the meantime, check out your wellness passport to see upcoming activities and track your progress!"
            )

        # Add a task nudge if available
        task_nudge = None
        if next_available_tasks:
            task = next_available_tasks[0]
            task_nudge = (
                f"By the way, you have '{task.title}' available to complete. "
                f"It's a great next step in your wellness journey!"
            )
            response += f"\n\n{task_nudge}"

        return GuideResponse(message=response, next_task_nudge=task_nudge)


def get_conversation_guide_service():
    """Dependency injection for ConversationGuideService."""
    from app.config import get_settings

    return ConversationGuideService(get_settings())
