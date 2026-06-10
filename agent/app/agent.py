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


async def get_engineer_profiles(ctx: Context) -> str:
    """Retrieves the list of available engineers and their expertise profiles.

    Args:
        ctx: Context automatically injected by ADK.

    Returns:
        A string formatted as a list of engineer emails and their expertises.
    """
    formatted = [
        f"- {email}: {expertise}"
        for email, expertise in INITIAL_ENGINEER_PROFILES.items()
    ]
    return "\n".join(formatted)


async def search_historical_feedback(ctx: Context, query: str) -> str:
    """Searches long-term memory for any historical feedback or routing preferences matching the query.

    Args:
        ctx: Context automatically injected by ADK.
        query: The search query, e.g. a component or service name to find routing feedback for.

    Returns:
        A string listing matching feedback rules, or a message indicating none were found.
    """
    try:
        response = await ctx.search_memory(query=query)
        if not response.memories:
            return "No matching historical feedback found."

        lines = []
        for i, entry in enumerate(response.memories, 1):
            if entry.content and entry.content.parts:
                text = " ".join(
                    [part.text for part in entry.content.parts if part.text]
                )
                lines.append(f"{i}. Feedback: {text}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching historical feedback: {str(e)}"


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are the GitHub Issue Triage & Assignment Assistant. "
        "Your task is to assign an incoming GitHub issue to the most suitable engineer. "
        "The default list of engineers is:\n"
        f"{', '.join(ENGINEERS)}\n\n"
        "To make the best decision:\n"
        "1. Always start by using the get_engineer_profiles tool to retrieve the known profiles of the available engineers.\n"
        "2. Always use the search_historical_feedback tool to query long-term memory with keywords related to the issue (such as service names, programming languages, or component names) to check for any custom routing preferences or feedback. Custom routing preferences or assignee specified in the historical feedback MUST take precedence over the default engineer profiles, even if they point to an assignee who is not in the default list of engineers.\n"
        "3. Match the issue's requirements against both the default profiles and the custom historical feedback.\n"
        "4. You MUST return a JSON object in this strict format, and nothing else:\n"
        "{\n"
        '  "assigned_engineer": "<email_id_of_chosen_engineer>",\n'
        '  "explanation": "<detailed_explanation_of_why_this_engineer_was_selected_based_on_retrieved_profiles_and_feedback>"\n'
        "}\n"
    ),
    tools=[get_engineer_profiles, search_historical_feedback],
)


app = App(
    root_agent=root_agent,
    name="app",
)
