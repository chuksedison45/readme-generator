#!/usr/bin/env python3
"""
Bedrock Agents CLI with Caching – Minimize AWS runtime costs.

Usage:
  bedrock_cli.py list                              # List available agents
  bedrock_cli.py invoke --agent <name> --input <text> [--no-cache] [--ttl <seconds>]
  bedrock_cli.py invoke --agent repo_scanner --repo <url> [--no-cache]
  bedrock_cli.py invoke --agent <name> --files <json> [--no-cache]

If no arguments are given, the script runs in interactive mode.
Caching:
- Responses are cached in ~/.bedrock_cache using a hash of agent ID and input.
- Cache entries expire after a default TTL (1 hour) but can be configured.
Agent IDs can be set via environment variables or a JSON config file at ~/.bedrock_agents.json.
Example ~/.bedrock_agents.json:
{
  "repo_scanner": "TSTAGENTID1",
  "project_summarizer": "TSTAGENTID2",
  "installation_guide": "TSTAGENTID3",
  "usage_examples": "TSTAGENTID4"
}

Example environment variables:
export REPO_SCANNER_AGENT_ID=TSTAGENTID1
export PROJECT_SUMMARIZER_AGENT_ID=TSTAGENTID2
export INSTALLATION_GUIDE_AGENT_ID=TSTAGENTID3
export USAGE_EXAMPLES_AGENT_ID=TSTAGENTID4

Example usage:
  bedrock_cli.py list
  bedrock_cli.py invoke --agent repo_scanner --repo https://github.com/TruLie13/municipal-ai
  bedrock_cli.py invoke --agent project_summarizer --files '[{"fileName": "file1.py", "content": "print(\"Hello\")"}]' --ttl 7200
  python bedrock_cli.py invoke --agent project_summarizer --files '{"files":[".gitignore","README.md"]}' --no-cache
  bedrock_cli.py invoke --agent installation_guide --files '{"files":[".gitignore","README.md"]}'
  bedrock_cli.py invoke --agent usage_examples --files '{"files":[".gitignore","README.md"]}'

"""

import boto3
import uuid
import json
import os
import sys
import argparse
import hashlib
import time
import re
from typing import Dict, Optional, Any, List

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DEFAULT_REGION = os.getenv("AWS_REGION", "us-east-1")
DEFAULT_ALIAS_ID = os.getenv("AGENT_ALIAS_ID", "TSTALIASID")
CACHE_DIR = os.path.expanduser("./.bedrock_cache")
DEFAULT_TTL = 3600  # 1 hour in seconds
CONFIG_FILE = os.path.expanduser("./.bedrock_agents.json")

os.makedirs(CACHE_DIR, exist_ok=True)

def load_agent_ids() -> Dict[str, str]:
    """Load agent IDs from environment variables or config file."""
    ids = {
        "repo_scanner": os.getenv("REPO_SCANNER_AGENT_ID"),
        "project_summarizer": os.getenv("PROJECT_SUMMARIZER_AGENT_ID"),
        "installation_guide": os.getenv("INSTALLATION_GUIDE_AGENT_ID"),
        "usage_examples": os.getenv("USAGE_EXAMPLES_AGENT_ID"),
    }
    if any(v is None for v in ids.values()):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                file_ids = json.load(f)
                for key in ids:
                    if ids[key] is None and key in file_ids:
                        ids[key] = file_ids[key]
    return ids

AGENT_IDS = load_agent_ids()

# ----------------------------------------------------------------------
# Cache functions
# ----------------------------------------------------------------------
def cache_key(agent_id: str, input_text: str) -> str:
    combined = f"{agent_id}:{input_text}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()

def get_from_cache(key: str, ttl: int) -> Optional[str]:
    cache_file = os.path.join(CACHE_DIR, key)
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
        timestamp = data.get("timestamp", 0)
        if time.time() - timestamp > ttl:
            os.remove(cache_file)
            return None
        return data.get("response")
    except Exception:
        return None

def save_to_cache(key: str, response: str):
    cache_file = os.path.join(CACHE_DIR, key)
    data = {"timestamp": time.time(), "response": response}
    try:
        with open(cache_file, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

# ----------------------------------------------------------------------
# Agent invocation
# ----------------------------------------------------------------------
def invoke_agent(agent_id: str, input_text: str, region: str = DEFAULT_REGION,
                 alias_id: str = DEFAULT_ALIAS_ID, use_cache: bool = True,
                 ttl: int = DEFAULT_TTL, debug: bool = False) -> str:
    if use_cache:
        key = cache_key(agent_id, input_text)
        cached = get_from_cache(key, ttl)
        if cached is not None:
            if debug:
                print(f"[DEBUG] Cache hit for key {key[:8]}...")
            return f"[CACHED]\n{cached}"

    if debug:
        print(f"[DEBUG] Invoking agent {agent_id} with input: {input_text[:100]}...")

    client = boto3.client("bedrock-agent-runtime", region_name=region)
    session_id = str(uuid.uuid4())

    try:
        response = client.invoke_agent(
            agentId=agent_id,
            agentAliasId=alias_id,
            sessionId=session_id,
            inputText=input_text,
        )
        result = ""
        for event in response.get("completion", []):
            if "chunk" in event:
                result += event["chunk"]["bytes"].decode("utf-8")
        if use_cache and result:
            save_to_cache(key, result)
        return result
    except Exception as e:
        return f"Error invoking agent {agent_id}: {str(e)}"

# ----------------------------------------------------------------------
# Helper functions for README generation
# ----------------------------------------------------------------------
def extract_repo_name(repo_url: str) -> str:
    """Extract repository name from GitHub URL."""
    repo_url = repo_url.rstrip('/')
    parts = repo_url.split('/')
    if len(parts) >= 2:
        return parts[-1]
    return "repository"

def parse_scanner_response(response: str, debug: bool = False) -> Dict[str, Any]:
    """Parse JSON from agent response, handling extra text and markdown fences."""
    raw_response = response
    response = response.strip()
    if response.startswith("[CACHED]"):
        response = response.split("\n", 1)[-1].strip()

    # Remove markdown code fences
    if response.startswith("```"):
        lines = response.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        response = "\n".join(lines).strip()

    # Try to find a JSON object
    import re
    match = re.search(r'(\{.*\})', response, re.DOTALL)
    if match:
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            if debug:
                print("[DEBUG] Found JSON-like string but failed to parse")

    # Fallback: try to parse whole response as JSON
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # If all else fails, try to extract a file list from plain text
    if debug:
        print("[DEBUG] Could not parse JSON, attempting plain text file list extraction")
    lines = raw_response.splitlines()
    file_tree = []
    for line in lines:
        line = line.strip()
        if line.startswith(("- ", "* ")):
            file_path = line[2:].strip()
            if file_path and not file_path.endswith("/"):
                file_tree.append(file_path)
        elif line and not line.startswith("The GitHub") and not line.startswith("```"):
            # Heuristic: contains dot or slash
            if "." in line or "/" in line:
                file_tree.append(line)

    if file_tree:
        return {
            "name": "",
            "description": "",
            "languages": {},
            "file_tree": file_tree,
            "default_branch": "main"
        }

    return {"error": "Could not parse scanner response", "raw": raw_response}

def assemble_readme(repo_name: str, scanner_data: Dict[str, Any],
                    summary: str, install: str, usage: str) -> str:
    """Assemble the final README content from agent outputs."""
    description = scanner_data.get("description", "")
    if not description:
        description = "No description provided."

    # Clean agent outputs
    summary = summary.replace("[CACHED]\n", "").strip()
    install = install.replace("[CACHED]\n", "").strip()
    usage = usage.replace("[CACHED]\n", "").strip()

    readme = f"# {repo_name}\n\n"
    readme += f"{description}\n\n"

    readme += "## Description\n"
    readme += summary + "\n\n"

    if "No dependency management file found." not in install:
        readme += install + "\n\n"
    else:
        readme += "## Installation\nNo specific installation instructions available.\n\n"

    if "Could not determine a main script." not in usage:
        readme += usage + "\n\n"
    else:
        readme += "## Usage\nNo usage instructions available.\n\n"

    readme += "## License\nThis project is licensed under the terms of the [LICENSE](LICENSE) file.\n"
    return readme

# ----------------------------------------------------------------------
# Command-line interface
# ----------------------------------------------------------------------
def list_agents():
    print("\nAvailable agents:")
    for name, agent_id in AGENT_IDS.items():
        status = agent_id if agent_id else "NOT CONFIGURED"
        print(f"  {name}: {status}")
    print("\nTo configure agent IDs, set environment variables or create ~/.bedrock_agents.json")

def read_input_from_string_or_file(value: str) -> str:
    """If value starts with '@', read from file; otherwise return as is."""
    if value.startswith('@'):
        file_path = value[1:]
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            sys.exit(1)
    return value

def invoke_cmd(args):
    agent_id = AGENT_IDS.get(args.agent)
    if not agent_id:
        print(f"Error: Agent '{args.agent}' not configured.")
        sys.exit(1)

    # Determine input text
    if args.repo:
        input_text = args.repo
    elif args.files:
        input_text = read_input_from_string_or_file(args.files)
    elif args.input:
        input_text = args.input
    else:
        print("Error: No input provided. Use --repo, --files, or --input.")
        sys.exit(1)

    use_cache = not args.no_cache
    ttl = args.ttl if args.ttl else DEFAULT_TTL

    print(f"\nInvoking agent '{args.agent}'...")
    response = invoke_agent(agent_id, input_text, args.region, args.alias_id,
                            use_cache, ttl, args.debug)
    if args.debug:
        print("\n[DEBUG] Raw response:")
        print(response)
        print("----------------")
    else:
        print("\n--- Response ---")
        print(response)
        print("----------------\n")

def generate_cmd(args):
    required_agents = ["repo_scanner", "project_summarizer", "installation_guide", "usage_examples"]
    missing = [a for a in required_agents if not AGENT_IDS.get(a)]
    if missing:
        print(f"Error: The following agents are not configured: {', '.join(missing)}")
        sys.exit(1)

    repo_url = args.repo
    output_dir = args.output
    use_cache = not args.no_cache
    ttl = args.ttl if args.ttl else DEFAULT_TTL
    debug = args.debug

    os.makedirs(output_dir, exist_ok=True)

    print(f"\nGenerating README for {repo_url}...")

    # Step 1: Invoke repo scanner
    print("  Scanning repository...")
    scanner_response = invoke_agent(
        AGENT_IDS["repo_scanner"], repo_url,
        region=args.region, alias_id=args.alias_id,
        use_cache=use_cache, ttl=ttl, debug=debug
    )
    scanner_data = parse_scanner_response(scanner_response, debug)
    if "error" in scanner_data:
        print(f"  Error from repo scanner: {scanner_data['error']}")
        if debug:
            print("  Raw scanner response:")
            print(scanner_response)
        sys.exit(1)

    file_tree = scanner_data.get("file_tree", [])
    if not file_tree:
        print("  Warning: No file tree returned. Using empty list.")
        file_tree = []

    files_input = json.dumps({"files": file_tree})

    # Step 2: Invoke project summarizer
    print("  Summarizing project...")
    summary = invoke_agent(
        AGENT_IDS["project_summarizer"], files_input,
        region=args.region, alias_id=args.alias_id,
        use_cache=use_cache, ttl=ttl, debug=debug
    )

    # Step 3: Invoke installation guide
    print("  Generating installation guide...")
    install = invoke_agent(
        AGENT_IDS["installation_guide"], files_input,
        region=args.region, alias_id=args.alias_id,
        use_cache=use_cache, ttl=ttl, debug=debug
    )

    # Step 4: Invoke usage examples
    print("  Generating usage examples...")
    usage = invoke_agent(
        AGENT_IDS["usage_examples"], files_input,
        region=args.region, alias_id=args.alias_id,
        use_cache=use_cache, ttl=ttl, debug=debug
    )

    # Step 5: Assemble README
    repo_name = extract_repo_name(repo_url)
    readme_content = assemble_readme(repo_name, scanner_data, summary, install, usage)

    # Step 6: Write to file
    output_file = os.path.join(output_dir, f"{repo_name}.md")
    with open(output_file, "w") as f:
        f.write(readme_content)

    print(f"\n✅ README generated successfully: {output_file}")

def interactive_mode():
    """Enhanced interactive mode with agent‑specific guidance."""
    print("\n" + "="*60)
    print("   Bedrock Agents Interactive CLI (Enhanced)")
    print("="*60)
    list_agents()

    while True:
        print("\n" + "-"*40)
        print("Main Menu:")
        print("  1. Invoke an agent")
        print("  2. Generate README for a repository")
        print("  3. List configured agents")
        print("  4. Clear cache")
        print("  5. Exit")
        choice = input("\nSelect option (1-5): ").strip()

        if choice == "1":
            # Agent selection with numbers
            agent_names = list(AGENT_IDS.keys())
            print("\nAvailable agents:")
            for i, name in enumerate(agent_names, 1):
                status = "✓" if AGENT_IDS[name] else "✗ (not configured)"
                print(f"  {i}. {name} {status}")
            print("  0. Back to main menu")

            agent_choice = input("\nSelect agent by number: ").strip()
            if agent_choice == "0":
                continue
            try:
                idx = int(agent_choice) - 1
                if idx < 0 or idx >= len(agent_names):
                    print("Invalid number.")
                    continue
                agent_name = agent_names[idx]
            except ValueError:
                print("Please enter a number.")
                continue

            if not AGENT_IDS[agent_name]:
                print(f"Agent '{agent_name}' is not configured. Please set its ID first.")
                continue

            # Agent-specific input collection
            print(f"\n--- Invoking {agent_name} ---")

            if agent_name == "repo_scanner":
                print("This agent expects a GitHub repository URL.")
                print("Example: https://github.com/owner/repo")
                inp = input("Enter URL: ").strip()
                # Basic URL validation
                if not inp.startswith(("https://github.com/", "http://github.com/")):
                    print("Warning: That doesn't look like a GitHub URL. Proceed anyway? (y/n)")
                    if input().strip().lower() != 'y':
                        continue
            else:
                print("This agent expects a JSON object with a 'files' key containing a list of file paths.")
                print("Example: {\"files\": [\"main.py\", \"README.md\", \"requirements.txt\"]}")
                print("\nYou can:")
                print("  - Type or paste the JSON directly")
                print("  - Use '@filename' to load from a file")
                print("  - Press Enter to load a sample template")

                inp = input("Input: ").strip()
                if inp == "":
                    # Provide a default template
                    inp = json.dumps({"files": ["main.py", "README.md", "requirements.txt"]})
                    print(f"Using template: {inp}")
                elif inp.startswith('@'):
                    try:
                        with open(inp[1:], 'r') as f:
                            inp = f.read()
                        print(f"Loaded from {inp[1:]}")
                    except Exception as e:
                        print(f"Error reading file: {e}")
                        continue

                # Validate JSON (optional – warn if invalid)
                try:
                    json.loads(inp)
                except json.JSONDecodeError:
                    print("Warning: Input is not valid JSON. The agent may not understand it.")
                    proceed = input("Proceed anyway? (y/n): ").strip().lower()
                    if proceed != 'y':
                        continue

            # Cache and debug options
            cache_choice = input("\nUse cache? (y/n, default y): ").strip().lower()
            use_cache = cache_choice != "n"
            ttl = DEFAULT_TTL
            if use_cache:
                ttl_input = input(f"Cache TTL in seconds (default {DEFAULT_TTL}): ").strip()
                if ttl_input.isdigit():
                    ttl = int(ttl_input)
            debug_choice = input("Enable debug output? (y/n, default n): ").strip().lower()
            debug = debug_choice == "y"

            print(f"\nInvoking {agent_name}...")
            response = invoke_agent(AGENT_IDS[agent_name], inp,
                                    use_cache=use_cache, ttl=ttl, debug=debug)
            if debug:
                print("\n[DEBUG] Raw response:")
                print(response)
            else:
                print("\n--- Response ---")
                print(response)
            print("----------------\n")

        elif choice == "2":
            repo_url = input("\nEnter GitHub repository URL: ").strip()
            if not repo_url.startswith(("https://github.com/", "http://github.com/")):
                print("Warning: That doesn't look like a GitHub URL.")
                if input("Proceed anyway? (y/n): ").strip().lower() != 'y':
                    continue
            output_dir = input("Output directory (default 'output'): ").strip() or "output"
            cache_choice = input("Use cache? (y/n, default y): ").strip().lower()
            use_cache = cache_choice != "n"
            ttl = DEFAULT_TTL
            if use_cache:
                ttl_input = input(f"Cache TTL in seconds (default {DEFAULT_TTL}): ").strip()
                if ttl_input.isdigit():
                    ttl = int(ttl_input)
            debug_choice = input("Enable debug output? (y/n, default n): ").strip().lower()
            debug = debug_choice == "y"

            # Create a simple args object
            class Args: pass
            args = Args()
            args.repo = repo_url
            args.output = output_dir
            args.no_cache = not use_cache
            args.ttl = ttl
            args.region = DEFAULT_REGION
            args.alias_id = DEFAULT_ALIAS_ID
            args.debug = debug

            generate_cmd(args)

        elif choice == "3":
            list_agents()
        elif choice == "4":
            confirm = input("Clear entire cache? (y/N): ").strip().lower()
            if confirm == "y":
                for f in os.listdir(CACHE_DIR):
                    os.remove(os.path.join(CACHE_DIR, f))
                print("Cache cleared.")
        elif choice == "5":
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 5.")

def main():
    parser = argparse.ArgumentParser(description="Bedrock Agents CLI")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    parser.add_argument("--alias-id", default=DEFAULT_ALIAS_ID, help="Agent alias ID")
    parser.add_argument("--debug", action="store_true", help="Print raw responses")

    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # List command
    subparsers.add_parser("list", help="List configured agents")

    # Invoke command
    invoke_parser = subparsers.add_parser("invoke", help="Invoke an agent")
    invoke_parser.add_argument("agent", choices=AGENT_IDS.keys(),
                               help="Agent to invoke")
    invoke_parser.add_argument("--repo", help="GitHub repository URL (for repo_scanner)")
    invoke_parser.add_argument("--files", help="JSON file list string or file path with @ prefix")
    invoke_parser.add_argument("--input", help="Raw input text (alternative to --repo/--files)")
    invoke_parser.add_argument("--no-cache", action="store_true", help="Bypass cache")
    invoke_parser.add_argument("--ttl", type=int, default=DEFAULT_TTL,
                               help=f"Cache TTL (default {DEFAULT_TTL}s)")

    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate README for a repo")
    generate_parser.add_argument("--repo", required=True, help="GitHub repository URL")
    generate_parser.add_argument("--output", default="output", help="Output directory (default: output/)")
    generate_parser.add_argument("--no-cache", action="store_true", help="Bypass cache")
    generate_parser.add_argument("--ttl", type=int, default=DEFAULT_TTL,
                                 help=f"Cache TTL (default {DEFAULT_TTL}s)")

    args = parser.parse_args()

    if args.command == "list":
        list_agents()
    elif args.command == "invoke":
        invoke_cmd(args)
    elif args.command == "generate":
        generate_cmd(args)
    else:
        interactive_mode()

if __name__ == "__main__":
    main()
