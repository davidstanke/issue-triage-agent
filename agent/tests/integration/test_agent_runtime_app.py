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
    async for event in agent_app.async_stream_query(
        message=message, user_id="github-issue-agent"
    ):
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


@pytest.mark.asyncio
async def test_agent_query_assignment(agent_app: AgentEngineApp) -> None:
    """Tests that a standard query produces a triaged issue JSON assignment."""
    query_text = "The button alignment is broken on Safari mobile."
    response = await agent_app.query(query=query_text)

    parsed = json.loads(response)
    assert "assigned_engineer" in parsed
    assert "explanation" in parsed
    assert parsed["assigned_engineer"] == "alexrivera-davidstanke"


@pytest.mark.asyncio
async def test_agent_feedback_and_retrieval(agent_app: AgentEngineApp) -> None:
    """Tests receiving feedback, storing it in memory, and routing based on it."""
    # 1. Submit feedback query
    feedback_query = (
        "FEEDBACK: This issue should have been assigned to john.doe@davidstanke.altostrat.com, "
        "because John has a lot of experience working in the checkout service and knows Java well."
    )
    feedback_response = await agent_app.query(query=feedback_query)
    parsed_feedback = json.loads(feedback_response)

    assert parsed_feedback["assigned_engineer"] == "john.doe@davidstanke.altostrat.com"
    assert (
        "Thank you for the feedback. I've added the following memory:"
        in parsed_feedback["explanation"]
    )
    assert "john.doe" in parsed_feedback["explanation"].lower()

    # 2. Submit standard query that matches the feedback keywords
    issue_query = "There is a NullPointerException in the checkout service backend when processing payments."
    issue_response = await agent_app.query(query=issue_query)
    parsed_issue = json.loads(issue_response)

    assert parsed_issue["assigned_engineer"] == "john.doe@davidstanke.altostrat.com"
    assert "john.doe@davidstanke.altostrat.com" in parsed_issue["explanation"]
