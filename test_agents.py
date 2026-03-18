#!/usr/bin/env python3
"""
Test script for the four Bedrock agents:
- Repo Scanner Agent
- Project Summarizer Agent
- Installation Guide Agent
- Usage Examples Agent
"""

import boto3
import uuid
import json
import os
from typing import Dict, Any

# -------------------- Configuration --------------------
REGION = os.getenv("AWS_REGION", "us-east-1")
AGENT_ALIAS_ID = os.getenv("AGENT_ALIAS_ID", "TSTALIASID")  # default test alias

# Replace with your actual agent IDs or set as environment variables
AGENT_IDS = {
    "repo_scanner": os.getenv("REPO_SCANNER_AGENT_ID", "replace-with-id"),
    "project_summarizer": os.getenv("PROJECT_SUMMARIZER_AGENT_ID", "replace-with-id"),
    "installation_guide": os.getenv("INSTALLATION_GUIDE_AGENT_ID", "replace-with-id"),
    "usage_examples": os.getenv("USAGE_EXAMPLES_AGENT_ID", "replace-with-id"),
}

# Sample inputs
SAMPLE_REPO_URL = "https://github.com/TruLie13/municipal-ai"  # change as needed
SAMPLE_FILE_LIST = {
    "files": [".gitignore", "README.md", "lambda_function.py", "requirements.txt"]
}
# For analytical agents, we send the file list as a JSON string
FILE_LIST_TEXT = json.dumps(SAMPLE_FILE_LIST)

# -------------------- Agent Invocation --------------------
def invoke_agent(agent_id: str, input_text: str) -> str:
    """Invoke a Bedrock Agent and return the complete response."""
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)
    session_id = str(uuid.uuid4())

    try:
        response = client.invoke_agent(
            agentId=agent_id,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=session_id,
            inputText=input_text,
        )

        result = ""
        for event in response.get("completion", []):
            if "chunk" in event:
                result += event["chunk"]["bytes"].decode("utf-8")
        return result
    except Exception as e:
        return f"Error invoking agent {agent_id}: {str(e)}"

# -------------------- Main --------------------
def main():
    print("=" * 60)
    print("Testing Bedrock Agents")
    print("=" * 60)

    # 1. Test Repo Scanner Agent
    print("\n>>> Repo Scanner Agent")
    print(f"Input: {SAMPLE_REPO_URL}")
    scanner_response = invoke_agent(AGENT_IDS["repo_scanner"], SAMPLE_REPO_URL)
    print("Response:")
    print(scanner_response)
    print("-" * 40)

    # 2. Test Project Summarizer Agent
    print("\n>>> Project Summarizer Agent")
    print(f"Input: {FILE_LIST_TEXT}")
    summary_response = invoke_agent(AGENT_IDS["project_summarizer"], FILE_LIST_TEXT)
    print("Response:")
    print(summary_response)
    print("-" * 40)

    # 3. Test Installation Guide Agent
    print("\n>>> Installation Guide Agent")
    print(f"Input: {FILE_LIST_TEXT}")
    install_response = invoke_agent(AGENT_IDS["installation_guide"], FILE_LIST_TEXT)
    print("Response:")
    print(install_response)
    print("-" * 40)

    # 4. Test Usage Examples Agent
    print("\n>>> Usage Examples Agent")
    print(f"Input: {FILE_LIST_TEXT}")
    usage_response = invoke_agent(AGENT_IDS["usage_examples"], FILE_LIST_TEXT)
    print("Response:")
    print(usage_response)
    print("-" * 40)

if __name__ == "__main__":
    main()
