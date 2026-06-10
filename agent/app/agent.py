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


from google.adk.tools import load_memory, preload_memory


async def save_session_to_memory(callback_context):
    try:
        await callback_context.add_session_to_memory()
    except ValueError:
        # Ignore if memory service is not configured (e.g. in tests)
        pass


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are the GitHub Issue Triage & Assignment Assistant.\n"
        "Your task is to assign an incoming GitHub issue to the most suitable engineer.\n"
        "The default list of engineers is:\n"
        f"{', '.join(ENGINEERS)}\n\n"
        "To make the best decision:\n"
        "1. Always start by using the get_engineer_profiles tool to retrieve the known profiles of the available engineers.\n"
        "2. Review the preloaded past conversation/feedback in the <PAST_CONVERSATIONS> context to check for any custom routing preferences or feedback. You may also use the load_memory or preload_memory tools if needed. Custom routing preferences or assignees specified in the historical feedback MUST take precedence over the default engineer profiles, even if they point to an assignee who is not in the default list of engineers.\n"
        "3. Match the issue's requirements against both the default profiles and any custom historical feedback.\n"
        "4. You MUST return a JSON object in this strict format, and nothing else:\n"
        "{\n"
        '  "assigned_engineer": "<email_id_of_chosen_engineer>",\n'
        '  "explanation": "<detailed_explanation_of_why_this_engineer_was_selected_based_on_retrieved_profiles_and_feedback>"\n'
        "}\n\n"
        "SPECIAL RULE FOR PROCESSING FEEDBACK:\n"
        "If the incoming message is user feedback, routing rules, or preferences (e.g., beginning with 'FEEDBACK:' or describing routing rules), your task is NOT to triage an issue. Instead, you must accept and save the feedback as a memory.\n"
        "Then, determine if the feedback included a preferred assignee. If it did, set assigned_engineer to that preferred engineer. If not, set assigned_engineer to '' (empty string).\n"
        "Then, you MUST output a JSON object in this exact format:\n"
        "{\n"
        '  "assigned_engineer": "<assigned_engineer>",\n'
        '  "explanation": "Thank you for the feedback. I\'ve added the following memory: <concise summary of the routing rule/preference described in the feedback>"\n'
        "}\n"
    ),
    tools=[get_engineer_profiles, load_memory, preload_memory],
    after_agent_callback=save_session_to_memory,
)


app = App(
    root_agent=root_agent,
    name="app",
)
