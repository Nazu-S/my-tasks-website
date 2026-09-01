"""Server-side AI provider boundary for task decomposition."""

import json
import os
from datetime import date

from google import genai


class AIProviderError(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def _validate_response(payload):
    try:
        suggestions = payload["suggestions"]

        if (
            not isinstance(suggestions, list)
            or not suggestions
            or len(suggestions) > 20
        ):
            raise ValueError

        validated = []

        for suggestion in suggestions:
            title = suggestion["title"]
            priority = suggestion["priority"]
            due_date = suggestion.get("due_date")

            if (
                not isinstance(title, str)
                or not title.strip()
                or len(title.strip()) > 200
            ):
                raise ValueError

            if priority not in {"low", "medium", "high"}:
                raise ValueError

            if due_date is not None:
                if not isinstance(due_date, str):
                    raise ValueError
                date.fromisoformat(due_date)

            validated.append(
                {
                    "title": title.strip(),
                    "priority": priority,
                    "due_date": due_date,
                }
            )

        return validated

    except (KeyError, TypeError, ValueError):
        raise AIProviderError(
            "The AI returned an invalid task list.",
            502,
        )


def generate_task_suggestions(goal, count=3):
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise AIProviderError(
            "Gemini AI is not configured. Please set GEMINI_API_KEY.",
            503,
        )

    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""
Break the user's goal into exactly {count} actionable tasks.

Return ONLY valid JSON in this exact structure:

{{
  "suggestions": [
    {{
      "title": "Task title",
      "priority": "low",
      "due_date": "YYYY-MM-DD"
    }}
  ]
}}

Rules:
- Each task must have a clear actionable title.
- priority must be exactly "low", "medium", or "high".
- due_date must be YYYY-MM-DD or null.
- Only infer a due date when it makes sense.
- Do not add extra fields.
- Today's date is {date.today().isoformat()}.

User's goal:
{goal}
"""

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        )

        content = response.text
        return _validate_response(json.loads(content))

    except Exception as error:
        print(f"Gemini API error: {error}")

        raise AIProviderError(
            "The Gemini AI service could not generate task suggestions. "
            "Please try again.",
            502,
        )
