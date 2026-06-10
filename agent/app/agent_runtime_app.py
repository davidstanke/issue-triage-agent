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
import asyncio
import json
import logging
import os
from typing import Any

import google.auth
import vertexai
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.cloud import logging as google_cloud_logging
from vertexai.agent_engines.templates.adk import AdkApp

from app.agent import ENGINEERS
from app.agent import app as adk_app
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

    async def _process_feedback_async(self, query_text: str, user_id: str) -> str:
        import json

        from google import genai
        from google.adk.events.event import Event
        from google.genai import types

        # 1. Formulate memory
        client = genai.Client()
        prompt = (
            "You are an expert parser for GitHub issue assignment feedback.\n"
            "Your goal is to extract the routing preferences from the feedback query.\n\n"
            f"Feedback query:\n{query_text}\n\n"
            "Extract and output a concise, clear routing rule or preference that summarizes this feedback.\n"
            "The rule should specify the target component, service, language, or topic, the preferred assignee, and the reasoning.\n"
            "Do NOT include extra, long issue details/logs. Focus on the core mapping.\n"
            "Example output format:\n"
            "Assign issues related to checkout service or Java to john.doe@davidstanke.altostrat.com because John has extensive experience in checkout and Java.\n\n"
            "Return only the concise rule text."
        )
        response = client.models.generate_content(
            model="gemini-flash-latest", contents=prompt
        )
        concise_rule = response.text.strip()

        # Ensure set_up has run so memory_service is initialized
        if not self._tmpl_attrs.get("memory_service"):
            self.set_up()

        memory_service = self._tmpl_attrs.get("memory_service")
        if memory_service:
            event = Event(
                author="user",
                content=types.Content(
                    role="user", parts=[types.Part.from_text(text=concise_rule)]
                ),
            )
            # Add to memory
            await memory_service.add_events_to_memory(
                app_name=self._app_name(), user_id=user_id, events=[event]
            )

        return json.dumps(
            {
                "assigned_engineer": "(none)",
                "explanation": f"Feedback received and saved: {concise_rule}",
            }
        )

    def _run_sync(self, coro):
        """Runs an async coroutine synchronously, avoiding the 'running event loop' error."""
        import concurrent.futures

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return asyncio.run(coro)

    async def async_stream_query(
        self,
        *,
        message: Any,
        user_id: str,
        session_id: str | None = None,
        session_events: list[dict[str, Any]] | None = None,
        run_config: dict[str, Any] | None = None,
        **kwargs,
    ):
        # Extract string message
        msg_str = ""
        if isinstance(message, str):
            msg_str = message
        elif isinstance(message, dict):
            try:
                msg_str = message.get("parts", [{}])[0].get("text", "")
            except Exception:
                pass

        if msg_str.strip().startswith("FEEDBACK:"):
            from google.adk.events.event import Event
            from google.genai import types
            from vertexai.agent_engines import _utils

            # Process feedback
            feedback_res = await self._process_feedback_async(msg_str, user_id)

            # Yield as final event
            event = Event(
                author="root_agent",
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=feedback_res)]
                ),
            )
            yield _utils.dump_event_for_json(event)
            return

        # Otherwise, call super's async_stream_query
        async for event in super().async_stream_query(
            message=message,
            user_id=user_id,
            session_id=session_id,
            session_events=session_events,
            run_config=run_config,
            **kwargs,
        ):
            yield event

    def stream_query(
        self,
        *,
        message: Any,
        user_id: str,
        session_id: str | None = None,
        run_config: dict[str, Any] | None = None,
        **kwargs,
    ):
        # Extract string message
        msg_str = ""
        if isinstance(message, str):
            msg_str = message
        elif isinstance(message, dict):
            try:
                msg_str = message.get("parts", [{}])[0].get("text", "")
            except Exception:
                pass

        if msg_str.strip().startswith("FEEDBACK:"):
            from google.adk.events.event import Event
            from google.genai import types
            from vertexai.agent_engines import _utils

            # Run feedback processing synchronously
            feedback_res = self._run_sync(
                self._process_feedback_async(msg_str, user_id)
            )

            # Yield as final event
            event = Event(
                author="root_agent",
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=feedback_res)]
                ),
            )
            yield _utils.dump_event_for_json(event)
            return

        # Otherwise, call super's stream_query
        for event in super().stream_query(
            message=message,
            user_id=user_id,
            session_id=session_id,
            run_config=run_config,
            **kwargs,
        ):
            yield event

    def query(
        self,
        *,
        query: str,
        user_id: str = "default-user",
        session_id: str | None = None,
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
                if (
                    not explanation
                    or not isinstance(explanation, str)
                    or not explanation.strip()
                ):
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

        return json.dumps(
            {"assigned_engineer": assigned_engineer, "explanation": explanation}
        )

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
