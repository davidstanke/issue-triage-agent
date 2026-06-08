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
import pytest
from google.adk.events.event import Event
from app.agent_runtime_app import AgentEngineApp


@pytest.fixture
def agent_app(monkeypatch: pytest.MonkeyPatch) -> AgentEngineApp:
    """Fixture to create and set up AgentEngineApp instance"""
    # Set integration test flag to mock external services
    monkeypatch.setenv("INTEGRATION_TEST", "TRUE")

    from app.agent_runtime_app import agent_runtime

    agent_runtime.set_up()
    return agent_runtime


@pytest.mark.asyncio
async def test_agent_stream_query(agent_app: AgentEngineApp) -> None:
    """
    Integration test for the agent stream query functionality.
    Tests that the agent returns valid streaming responses.
    """
    message = "Need to construct dynamic UI and responsive CSS layouts."
    events = []
    async for event in agent_app.async_stream_query(message=message, user_id="github-issue-agent"):
        events.append(event)
    assert len(events) > 0, "Expected at least one chunk in response"

    has_text_content = False
    for event in events:
        validated_event = Event.model_validate(event)
        content = validated_event.content
        if (
            content is not None
            and content.parts
            and any(part.text for part in content.parts)
        ):
            has_text_content = True
            break

    assert has_text_content, "Expected at least one event with text content"


def test_agent_query_assignment(agent_app: AgentEngineApp) -> None:
    """Tests that a standard query produces a triaged issue JSON assignment."""
    query_text = "The button alignment is broken on Safari mobile."
    response = agent_app.query(query=query_text)

    parsed = json.loads(response)
    assert "assigned_engineer" in parsed
    assert "explanation" in parsed
    assert parsed["assigned_engineer"] == "alexrivera-davidstanke"
