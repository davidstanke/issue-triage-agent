# ruff: noqa
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

import os
import google.auth
from google.adk.agents import Agent
from google.adk import Context
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# Hardcoded list of 15 engineers
ENGINEERS = [
    "alexrivera-davidstanke",
    "beatricevance-davidstanke",
    "charliewu-davidstanke",
    "danielasilva-davidstanke",
    "eliaskline-davidstanke",
    "fionagallagher-davidstanke",
    "georgepatel-davidstanke",
]

# Standard initial expertise profiles
INITIAL_ENGINEER_PROFILES = {
    "alexrivera-davidstanke": "Frontend, React, HTML, CSS, layouts, UI designs, responsiveness",
    "beatricevance-davidstanke": "Backend APIs, FastAPI, Flask, REST endpoints, HTTP requests, web frameworks",
    "charliewu-davidstanke": "Databases, SQL, PostgreSQL, database migrations, schema design, query optimization, indexing",
    "danielasilva-davidstanke": "Cloud Infrastructure, DevOps, Terraform, Docker, Kubernetes, GCP, deployment pipelines",
    "eliaskline-davidstanke": "Security, Authentication, OAuth, IAM, JWT, encryption, SSL/TLS, vulnerabilities",
    "fionagallagher-davidstanke": "Testing, Pytest, unit tests, integration tests, mock objects, test coverage, CI workflows",
    "georgepatel-davidstanke": "Performance, Latency, caching, Redis, profiling, performance tuning, optimization",
}


async def search_past_issue_assignments(query: str, ctx: Context) -> str:
    """Searches the agent's memory bank for past issue assignments and profiles.

    Args:
        query: The search query (e.g. topic, issue text, keywords).
        ctx: Context automatically injected by ADK.

    Returns:
        A list of matching memories formatted as a string.
    """
    try:
        # Lazily seed memories if empty on first search to cover all environments/runners
        results = await ctx.search_memory("*")
        if not results or not results.memories:
            from google.adk.memory.memory_entry import MemoryEntry
            from google.genai import types

            initial_memories = [
                MemoryEntry(content=types.Content(parts=[types.Part(text=f"Engineer {email} is an expert in: {expertise}")]))
                for email, expertise in INITIAL_ENGINEER_PROFILES.items()
            ]
            try:
                await ctx.add_memory(memories=initial_memories)
            except (NotImplementedError, ValueError):
                from google.adk.events.event import Event
                events = [
                    Event(
                        id=f"seed-{i}",
                        author="github-issue-agent",
                        content=m.content,
                    )
                    for i, m in enumerate(initial_memories)
                ]
                await ctx.add_events_to_memory(events=events)

            results = await ctx.search_memory(query)
        else:
            results = await ctx.search_memory(query)

        if not results or not results.memories:
            return "No past memories found for this query."
        
        formatted = []
        for m in results.memories:
            text = "".join(part.text for part in m.content.parts if part.text)
            formatted.append(f"- {text}")
        return "\n".join(formatted)
    except Exception as e:
        return f"Error searching past assignments: {str(e)}"


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are the GitHub Issue Triage & Assignment Assistant. "
        "Your task is to assign an incoming GitHub issue to the most suitable engineer from the list of 15 available engineers:\n"
        f"{', '.join(ENGINEERS)}\n\n"
        "To make the best decision:\n"
        "1. Always start by using the search_past_issue_assignments tool to search for past assignments, successes, failures, and expertise profiles related to the current issue topic.\n"
        "2. Match the issue's requirements against the retrieved memories and the known profiles of the 15 engineers.\n"
        "3. You MUST return a JSON object in this strict format, and nothing else:\n"
        "{\n"
        '  "assigned_engineer": "<email_id_of_chosen_engineer>",\n'
        '  "explanation": "<detailed_explanation_of_why_this_engineer_was_selected_based_on_retrieved_memories_and_expertise>"\n'
        "}\n"
    ),
    tools=[search_past_issue_assignments],
)

app = App(
    root_agent=root_agent,
    name="app",
)
