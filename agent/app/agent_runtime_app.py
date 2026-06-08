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
import threading
from concurrent.futures import Future
from typing import Any, Optional

import google.auth
import vertexai
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.adk.memory import InMemoryMemoryService, VertexAiMemoryBankService
from google.cloud import logging as google_cloud_logging
from vertexai.agent_engines.templates.adk import AdkApp

from app.agent import app as adk_app
from app.agent import ENGINEERS, INITIAL_ENGINEER_PROFILES
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

# Load environment variables from .env file at runtime
try:
    _, project_id = google.auth.default()
except Exception:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or "mock-project"


def run_sync(coro):
    """Runs a coroutine synchronously, even when an event loop is already running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        def run_in_thread(future, c):
            try:
                res = asyncio.run(c)
                future.set_result(res)
            except Exception as e:
                future.set_result(e)

        f = Future()
        t = threading.Thread(target=run_in_thread, args=(f, coro))
        t.start()
        t.join()
        res = f.result()
        if isinstance(res, Exception):
            raise res
        return res
    else:
        return asyncio.run(coro)


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
        self._memories_seeded = False

    def register_feedback(self, feedback: dict[str, Any]) -> None:
        """Collect and log feedback."""
        feedback_obj = Feedback.model_validate(feedback)
        self.logger.log_struct(feedback_obj.model_dump(), severity="INFO")

    def seed_initial_memories_if_empty(self) -> None:
        """Seeds the memory bank with initial engineer profiles if it's currently empty."""
        if getattr(self, "_memories_seeded", False):
            return

        try:
            memory_service = self._tmpl_attrs.get("memory_service")
            app_name = self._tmpl_attrs.get("app_name") or "default-app-name"
            if not memory_service:
                return

            # Check if memories exist by doing a search
            results = run_sync(memory_service.search_memory(
                app_name=app_name,
                user_id="github-issue-agent",
                query="*"
            ))
            if not results or not results.memories:
                logging.info("Memory bank is empty. Seeding initial engineer profiles...")
                from google.adk.memory.memory_entry import MemoryEntry
                from google.genai import types

                initial_memories = [
                    MemoryEntry(content=types.Content(parts=[types.Part(text=f"Engineer {email} is an expert in: {expertise}")]))
                    for email, expertise in INITIAL_ENGINEER_PROFILES.items()
                ]
                try:
                    run_sync(memory_service.add_memory(
                        app_name=app_name,
                        user_id="github-issue-agent",
                        memories=initial_memories
                    ))
                except (NotImplementedError, ValueError):
                    # Fallback for InMemoryMemoryService
                    from google.adk.events.event import Event
                    events = [
                        Event(
                            id=f"seed-{i}",
                            author="github-issue-agent",
                            content=m.content,
                        )
                        for i, m in enumerate(initial_memories)
                    ]
                    run_sync(memory_service.add_events_to_memory(
                        app_name=app_name,
                        user_id="github-issue-agent",
                        events=events
                    ))
                logging.info("Seeded 15 initial engineer profiles successfully.")
            self._memories_seeded = True
        except Exception as e:
            logging.error(f"Error seeding initial memories: {str(e)}")

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
            query: The query string (issue text or JSON feedback) to send to the agent.
            user_id: The ID of the user.
            session_id: The ID of the session.
            **kwargs: Additional keyword arguments.

        Returns:
            The final text output of the agent or feedback acknowledgement.
        """
        # Ensure initial memories are seeded
        self.seed_initial_memories_if_empty()

        # Check if the query is a JSON feedback payload
        try:
            payload = json.loads(query)
            if isinstance(payload, dict) and payload.get("type") == "feedback":
                # Process feedback
                status = payload.get("status")
                assigned = payload.get("assigned_engineer")
                issue_text = payload.get("issue_text")
                preferred = payload.get("preferred_engineer")
                reason = payload.get("reason")

                memory_service = self._tmpl_attrs.get("memory_service")
                app_name = self._tmpl_attrs.get("app_name") or "default-app-name"

                if memory_service:
                    from google.adk.memory.memory_entry import MemoryEntry
                    from google.genai import types

                    memories_to_add = []
                    if status == "good":
                        text = f"Assignment was good: Engineer {assigned} successfully resolved issue: {issue_text}"
                        memories_to_add.append(
                            MemoryEntry(content=types.Content(parts=[types.Part(text=text)]))
                        )
                    elif status == "bad":
                        text_bad = f"Assignment was bad: Engineer {assigned} was not optimal for issue: {issue_text}. Preferred engineer: {preferred} because: {reason}"
                        memories_to_add.append(
                            MemoryEntry(content=types.Content(parts=[types.Part(text=text_bad)]))
                        )
                        if preferred:
                            text_pref = f"Assignment was preferred: Engineer {preferred} is preferred for issue: {issue_text}. Reason: {reason}"
                            memories_to_add.append(
                                MemoryEntry(content=types.Content(parts=[types.Part(text=text_pref)]))
                            )

                    if memories_to_add:
                        try:
                            run_sync(memory_service.add_memory(
                                app_name=app_name,
                                user_id="github-issue-agent",
                                memories=memories_to_add
                            ))
                        except (NotImplementedError, ValueError):
                            # Fallback for InMemoryMemoryService
                            from google.adk.events.event import Event
                            import time
                            events = [
                                Event(
                                    id=f"fb-{int(time.time() * 1000)}-{i}",
                                    author="github-issue-agent",
                                    content=m.content,
                                )
                                for i, m in enumerate(memories_to_add)
                            ]
                            run_sync(memory_service.add_events_to_memory(
                                app_name=app_name,
                                user_id="github-issue-agent",
                                events=events
                            ))

                return "thanks for the feedback"
        except (json.JSONDecodeError, TypeError):
            pass

        # Otherwise, run normal triage query using global user_id
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
        operations[""] = [*operations.get("", []), "register_feedback", "query"]
        return operations


def build_memory_service():
    engine_id = os.environ.get("AIP_REASONING_ENGINE_ID")
    if engine_id and (os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("LOGS_BUCKET_NAME")):
        try:
            return VertexAiMemoryBankService(
                project=project_id,
                location=gemini_location,
                agent_engine_id=engine_id
            )
        except Exception as e:
            logging.error(f"Failed to initialize VertexAiMemoryBankService: {e}. Falling back to InMemoryMemoryService.")
    return InMemoryMemoryService()


gemini_location = os.environ.get("GOOGLE_CLOUD_LOCATION")
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")
agent_runtime = AgentEngineApp(
    app=adk_app,
    artifact_service_builder=lambda: (
        GcsArtifactService(bucket_name=logs_bucket_name)
        if logs_bucket_name
        else InMemoryArtifactService()
    ),
    memory_service_builder=build_memory_service,
)
