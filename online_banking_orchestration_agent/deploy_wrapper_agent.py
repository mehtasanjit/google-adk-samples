"""
Deploy a configurable Google ADK agent to Vertex AI Agent Engine.

This script creates and deploys an ADK agent to Vertex AI Agent Engine with
customizable parameters including agent name, model, and instruction.

Dependencies (install in your Cloud Shell, Workbench, or local env):
    pip install "google-cloud-aiplatform[adk,agent_engines]" vertexai python-dotenv

Example:
    python deploy_wrapper_agent.py \
        --project my-gcp-project \
        --region us-central1 \
        --bucket gs://my-vertex-staging-bucket \
        --agent_name "session-wrapper" \
        --model "gemini-2.5-flash" \
        --description "Session & Memory wrapper for ADK session and memory demo"

Notes
-----
* The script initializes Vertex AI, builds the configurable root agent, then creates
  an Agent Engine revision. The resulting resource name (and a handy Console
  URI) is printed so you can wire clients to it with:
      --session_service_uri="agentengine://<resource_name>"
  and memory with:
      --memory_service_uri="agentengine://<resource_name>"
* IAM: the caller must have Vertex AI Admin (or Deployer) role.
* The client (e.g., Cloud Run) connecting to this Agent Engine needs roles/aiplatform.user.
* You can also use environment variables (.env.dev) to set default values.
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

import vertexai
from vertexai import agent_engines

try:
    from google.adk.agents import Agent  # type: ignore
except ImportError as exc:
    sys.exit(
        "google-adk is not installed. Run: pip install google-cloud-aiplatform[adk,agent_engines]"
    )

# Try to load environment variables if .env.dev exists
try:
    from dotenv import load_dotenv  # type: ignore

    dotenv_path = Path(".env.dev")
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
        print("INFO: Loaded environment variables from .env.dev")
except Exception:
    print("INFO: python-dotenv not available or .env.dev missing; continuing")


def deploy_agent(
    project: str,
    region: str,
    bucket: str,
    agent_name: str = "session-and-memory-wrapper",
    model: str = "gemini-2.5-flash",
    instruction: str | None = None,
    description: str | None = None,
    display_name: str | None = None,
) -> str:
    """Creates the Agent Engine and returns its resource name.

    Args:
        project: GCP project ID
        region: GCP region (e.g., us-central1)
        bucket: GCS bucket for Vertex AI staging
        agent_name: Internal name for the agent
        model: Foundation model backing the agent
        instruction: Custom instruction for the agent
        description: Description for the Agent Engine
        display_name: Display name for the Agent Engine

    Returns:
        The resource name of the deployed Agent Engine
    """

    print(f"INFO: Starting deployment of agent '{agent_name}'...")
    print(f"INFO: Project: {project}")
    print(f"INFO: Region: {region}")
    print(f"INFO: Staging Bucket: {bucket}")
    print(f"INFO: Model: {model}")

    try:
        vertexai.init(project=project, location=region, staging_bucket=bucket)
        print("INFO: Vertex AI initialized successfully")

        if instruction is None:
            instruction = (
                "You are a wrapper agent for a netbanking demo. "
                "Your purpose is session and memory management and coordination only. "
                "Do not reply directly to end users; delegate to specialized subagents/services."
            )

        if description is None:
            description = (
                f"Netbanking Wrapper Agent for Session/Memory Management ({agent_name})"
            )

        if display_name is None:
            display_name = f"{agent_name}-ae"

        print("INFO: Creating ADK agent definition")
        root_agent = Agent(
            name=agent_name,
            model=model,
            instruction=instruction,
        )

        print("INFO: Deploying to Vertex AI Agent Engine...")
        engine = agent_engines.create(
            agent_engine=root_agent,
            display_name=display_name,
            description=description,
            requirements=[
                "google-cloud-aiplatform[adk,agent_engines]",
                "google-adk",
                "google-genai",
            ],
        )

        print("INFO: Agent Engine deployed successfully!")
        print("=" * 60)
        print("INFO: DEPLOYMENT SUCCESSFUL!")
        print("=" * 60)
        print("INFO: Agent Details:")
        print(f"   • Agent Name    : {agent_name}")
        print(f"   • Display Name  : {display_name}")
        print(f"   • Model         : {model}")
        print(f"   • Resource Name : {engine.resource_name}")
        print("INFO: Usage:")
        print(
            f"   • Use as session or memory backend URI: agentengine://{engine.resource_name}"
        )
        return engine.resource_name

    except Exception as e:  # noqa: BLE001
        print(f"ERROR: Failed to deploy agent: {str(e)}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy a configurable ADK agent to Vertex AI Agent Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT"),
        help="GCP project ID (or set GOOGLE_CLOUD_PROJECT_ID/GOOGLE_CLOUD_PROJECT)",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("GOOGLE_CLOUD_LOCATION_ID") or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        help="GCP region (default from env or us-central1)",
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("GOOGLE_CLOUD_STAGING_BUCKET"),
        help="GCS staging bucket (format gs://bucket)",
    )

    parser.add_argument(
        "--agent_name",
        default="session-wrapper",
        help="Internal name for the agent",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="Foundation model backing the agent",
    )
    parser.add_argument(
        "--instruction",
        help="Custom instruction for the agent",
    )
    parser.add_argument(
        "--description",
        help="Description for the Agent Engine",
    )
    parser.add_argument(
        "--display_name",
        help="Display name for the Agent Engine",
    )

    args = parser.parse_args()

    missing: list[str] = []
    if not args.project:
        missing.append("--project (or GOOGLE_CLOUD_PROJECT[ _ID])")
    if not args.region:
        missing.append("--region (or GOOGLE_CLOUD_LOCATION[ _ID])")
    if not args.bucket:
        missing.append("--bucket (or GOOGLE_CLOUD_STAGING_BUCKET)")

    if missing:
        print("ERROR: Missing required arguments:")
        for m in missing:
            print(f"  • {m}")
        sys.exit(1)

    if not args.bucket.startswith("gs://"):
        print("ERROR: --bucket must be in format gs://bucket-name")
        sys.exit(1)

    resource_name = deploy_agent(
        project=args.project,
        region=args.region,
        bucket=args.bucket,
        agent_name=args.agent_name,
        model=args.model,
        instruction=args.instruction,
        description=args.description,
        display_name=args.display_name,
    )

    print(f"INFO: Agent Engine resource name: {resource_name}")


if __name__ == "__main__":
    main() 
