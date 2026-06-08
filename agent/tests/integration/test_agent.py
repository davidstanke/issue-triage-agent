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
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.genai import types

from app.agent import root_agent


def test_agent_stream() -> None:
    """
    Integration test for the agent stream functionality.
    Tests that the agent returns valid streaming responses for issue assignments.
    """

    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()

    session = session_service.create_session_sync(user_id="github-issue-agent", app_name="test")
    runner = Runner(
        agent=root_agent,
        session_service=session_service,
        memory_service=memory_service,
        app_name="test"
    )

    message = types.Content(
        role="user", parts=[types.Part.from_text(text="Our PostgreSQL database is throwing deadlock exceptions during schema migrations.")]
    )

    events = list(
        runner.run(
            new_message=message,
            user_id="github-issue-agent",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )
    assert len(events) > 0, "Expected at least one message"

    response_text = ""
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text += part.text

    print(f"\n>>> Agent Response:\n{response_text}\n")
    
    # Charlie Wu is our database/migration expert
    assert "charliewu-davidstanke" in response_text


def test_agent_memory_retrieval() -> None:
    """
    Integration test verifying that the agent can retrieve and leverage past
    memories/expert profiles from its memory.
    """
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    session = session_service.create_session_sync(user_id="github-issue-agent", app_name="test")
    runner = Runner(
        agent=root_agent,
        session_service=session_service,
        memory_service=memory_service,
        app_name="test"
    )

    # Let's run a query about performance and caching
    message = types.Content(
        role="user", parts=[types.Part.from_text(text="Our main landing page has high latency; we need to add Redis caching.")]
    )

    events = list(
        runner.run(
            new_message=message,
            user_id="github-issue-agent",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )
    
    response_text = ""
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text += part.text

    print(f"\n>>> Agent Response:\n{response_text}\n")
    
    # George Patel is our performance expert
    assert "georgepatel-davidstanke" in response_text
