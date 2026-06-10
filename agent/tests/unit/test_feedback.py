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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent import app as adk_app
from app.agent_runtime_app import AgentEngineApp


@pytest.fixture
def mock_agent_app(monkeypatch):
    monkeypatch.setenv("INTEGRATION_TEST", "TRUE")
    with (
        patch("vertexai.init"),
        patch("app.agent_runtime_app.google_cloud_logging.Client"),
    ):
        app_instance = AgentEngineApp(app=adk_app)
        app_instance.logger = MagicMock()
        return app_instance


@pytest.mark.asyncio
async def test_process_feedback_async(mock_agent_app) -> None:
    # Mock Google GenAI Client
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Assign database issues to john.doe@davidstanke.altostrat.com because they are expert in Postgres"
    mock_genai_client.models.generate_content.return_value = mock_response

    # Mock Memory Service
    mock_memory_service = AsyncMock()
    mock_agent_app._tmpl_attrs["memory_service"] = mock_memory_service

    with (
        patch("google.genai.Client", return_value=mock_genai_client),
    ):
        res = await mock_agent_app._process_feedback_async(
            "FEEDBACK: assign database stuff to john.doe@davidstanke.altostrat.com",
            user_id="github-issue-agent",
        )

        # Verify parsed response
        parsed = json.loads(res)
        assert parsed["assigned_engineer"] == "(none)"
        assert "Feedback received and saved:" in parsed["explanation"]
        assert "john.doe" in parsed["explanation"]

        # Verify genai client prompt call
        mock_genai_client.models.generate_content.assert_called_once()

        # Verify memory service add_events_to_memory call
        mock_memory_service.add_events_to_memory.assert_called_once()
        called_kwargs = mock_memory_service.add_events_to_memory.call_args[1]
        assert called_kwargs["user_id"] == "github-issue-agent"
        assert len(called_kwargs["events"]) == 1
        event = called_kwargs["events"][0]
        assert event.author == "user"
        assert (
            event.content.parts[0].text
            == "Assign database issues to john.doe@davidstanke.altostrat.com because they are expert in Postgres"
        )


def test_query_intercepts_feedback(mock_agent_app) -> None:
    # Mock Google GenAI Client and memory
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Assign database issues to john.doe@davidstanke.altostrat.com"
    mock_genai_client.models.generate_content.return_value = mock_response

    mock_memory_service = AsyncMock()
    mock_agent_app._tmpl_attrs["memory_service"] = mock_memory_service

    with (
        patch("google.genai.Client", return_value=mock_genai_client),
    ):
        # Query with feedback
        res = mock_agent_app.query(
            query="FEEDBACK: assign database to john.doe@davidstanke.altostrat.com",
            user_id="github-issue-agent",
        )

        # Verify response structure
        parsed = json.loads(res)
        assert parsed["assigned_engineer"] == "(none)"
        assert "Feedback received and saved:" in parsed["explanation"]
        assert "john.doe" in parsed["explanation"]
