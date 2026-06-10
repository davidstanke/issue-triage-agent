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
from unittest.mock import MagicMock, patch

import pytest

from app.agent import app as adk_app
from app.agent_runtime_app import AgentEngineApp


class MockEvent:
    def __init__(self, text, is_final=True):
        self.text = text
        self.is_final = is_final

    def is_final_response(self):
        return self.is_final

    @property
    def content(self):
        outer_text = self.text

        class Content:
            @property
            def parts(self):
                class Part:
                    @property
                    def text(self):
                        return self._text

                    def __init__(self, t):
                        self._text = t

                return [Part(outer_text)]

        return Content()


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


def test_query_explanation_present_and_valid(mock_agent_app):
    # JSON containing valid assigned_engineer and explanation
    raw_response = '```json\n{"assigned_engineer": "charliewu-davidstanke", "explanation": "Expert in database migrations"}\n```'

    mock_event = {"id": "1", "content": {"parts": [{"text": raw_response}]}}

    with (
        patch.object(mock_agent_app, "stream_query", return_value=[mock_event]),
        patch(
            "google.adk.events.event.Event.model_validate",
            return_value=MockEvent(raw_response),
        ),
    ):
        res = mock_agent_app.query(query="Some migration issue")
        parsed = json.loads(res)
        assert parsed["assigned_engineer"] == "charliewu-davidstanke"
        assert parsed["explanation"] == "Expert in database migrations"


def test_query_explanation_missing_but_engineer_present(mock_agent_app):
    # JSON missing explanation, should fall back to "(unspecified)"
    raw_response = '```json\n{"assigned_engineer": "charliewu-davidstanke"}\n```'

    mock_event = {"id": "1", "content": {"parts": [{"text": raw_response}]}}

    with (
        patch.object(mock_agent_app, "stream_query", return_value=[mock_event]),
        patch(
            "google.adk.events.event.Event.model_validate",
            return_value=MockEvent(raw_response),
        ),
    ):
        res = mock_agent_app.query(query="Some migration issue")
        parsed = json.loads(res)
        assert parsed["assigned_engineer"] == "charliewu-davidstanke"
        assert parsed["explanation"] == "(unspecified)"


def test_query_explanation_empty_string(mock_agent_app):
    # JSON with empty/whitespace explanation, should fall back to "(unspecified)"
    raw_response = '```json\n{"assigned_engineer": "charliewu-davidstanke", "explanation": "   "}\n```'

    mock_event = {"id": "1", "content": {"parts": [{"text": raw_response}]}}

    with (
        patch.object(mock_agent_app, "stream_query", return_value=[mock_event]),
        patch(
            "google.adk.events.event.Event.model_validate",
            return_value=MockEvent(raw_response),
        ),
    ):
        res = mock_agent_app.query(query="Some migration issue")
        parsed = json.loads(res)
        assert parsed["assigned_engineer"] == "charliewu-davidstanke"
        assert parsed["explanation"] == "(unspecified)"


def test_query_invalid_json_fallback_with_text(mock_agent_app):
    # Not valid JSON but has email in text. Raw response should be the explanation.
    raw_response = (
        "We recommend assigning to charliewu-davidstanke because they are great."
    )

    mock_event = {"id": "1", "content": {"parts": [{"text": raw_response}]}}

    with (
        patch.object(mock_agent_app, "stream_query", return_value=[mock_event]),
        patch(
            "google.adk.events.event.Event.model_validate",
            return_value=MockEvent(raw_response),
        ),
    ):
        res = mock_agent_app.query(query="Some migration issue")
        parsed = json.loads(res)
        assert parsed["assigned_engineer"] == "charliewu-davidstanke"
        assert parsed["explanation"] == raw_response


def test_query_invalid_json_fallback_empty_response(mock_agent_app):
    # Empty response, should fall back to default engineer and "(unspecified)"
    raw_response = "   "

    mock_event = {"id": "1", "content": {"parts": [{"text": raw_response}]}}

    with (
        patch.object(mock_agent_app, "stream_query", return_value=[mock_event]),
        patch(
            "google.adk.events.event.Event.model_validate",
            return_value=MockEvent(raw_response),
        ),
    ):
        res = mock_agent_app.query(query="Some migration issue")
        parsed = json.loads(res)
        # Should default to the first engineer (alexrivera-davidstanke)
        assert parsed["assigned_engineer"] == "alexrivera-davidstanke"
        assert parsed["explanation"] == "(unspecified)"
