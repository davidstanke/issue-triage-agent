# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import logging
import os
import asyncio
from typing import Any, Optional

import google.auth
import vertexai
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.cloud import logging as google_cloud_logging
from vertexai.agent_engines.templates.adk import AdkApp

from app.agent import app as adk_app
from app.agent import ENGINEERS, INITIAL_ENGINEER_PROFILES
from app.app_utils.telemetry import setup_telemetry

# Load environment variables from .env file at runtime
try:
    _, project_id = google.auth.default()
except Exception:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or "mock-project"


class AgentEngineApp(AdkApp):
    def set_up(self) -> None:
        """Initialize the agent engine app with logging and telemetry."""
        vertexai.init()
        setup_telemetry()
        super().set_up()
        logging.basicConfig(level=logging.INFO)
        logging_client = google_cloud_logging.Client()
        self.logger = logging_client.logger(__name__)
        if gemini_location:
            os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_location

    def query(
        self,
        *,
        query: str,
        user_id: str = "default-user",
        session_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Runs a synchronous, non-streaming query against the agent.

        Args:
            query: The query string to send to the agent.
            user_id: The ID of the user.
            session_id: The ID of the session.
            **kwargs: Additional keyword arguments.

        Returns:
            The final text output of the agent.
        """

        from google.adk.events.event import Event

        response_parts = []
        for event_dict in self.stream_query(
            message=query,
            user_id="github-issue-agent",
            session_id=session_id,
            **kwargs,
        ):
            event = Event.model_validate(event_dict)
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_parts.append(part.text)

        raw_response = "".join(response_parts)

        # Parse and sanitize response to return a strictly conforming JSON string
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "assigned_engineer" in parsed:
                explanation = parsed.get("explanation")
                if not explanation or not isinstance(explanation, str) or not explanation.strip():
                    parsed["explanation"] = "(unspecified)"
                return json.dumps(parsed)
        except Exception:
            pass

        # Fallback to structure raw output
        assigned_engineer = ENGINEERS[0]
        for email in ENGINEERS:
            if email in raw_response:
                assigned_engineer = email
                break

        explanation = raw_response.strip() if raw_response else ""
        if not explanation:
            explanation = "(unspecified)"

        return json.dumps({
            "assigned_engineer": assigned_engineer,
            "explanation": explanation
        })

    def register_operations(self) -> dict[str, list[str]]:
        """Registers the operations of the Agent."""
        operations = super().register_operations()
        operations[""] = [*operations.get("", []), "query"]
        return operations


gemini_location = os.environ.get("GOOGLE_CLOUD_LOCATION")
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")
agent_runtime = AgentEngineApp(
    app=adk_app,
    artifact_service_builder=lambda: (
        GcsArtifactService(bucket_name=logs_bucket_name)
        if logs_bucket_name
        else InMemoryArtifactService()
    ),
)
