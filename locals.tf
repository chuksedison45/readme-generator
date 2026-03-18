# ----------------------------------------------------------------------
# Local values defining all agents and their prompts
# ----------------------------------------------------------------------
locals {
  agents = {
    repo_scanner = {
      name        = "ed45-Repo_Scanner_Agent"
      instruction = <<-EOT
        You are a repository analysis tool. Your task is to accept a GitHub repository URL, invoke the scanner tool to fetch its metadata and file tree, and then return a **JSON object** with the following keys:
        - "name": repository name
        - "description": repository description (if any)
        - "languages": a dictionary of languages and bytes used
        - "file_tree": a list of all file paths in the root directory
        - "default_branch": the default branch name

        Do not add any explanatory text. Output **only** the JSON object.
      EOT
      # For the scanner, we also need an action group attached to the Lambda.
      # This is handled in the module via a variable `action_group_uri`.
      action_group_uri = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${aws_lambda_function.repo_scanner_lambda.function_name}"
    }
    project_summarizer = {
      name        = "ed45-Project_Summarizer_Agent"
      instruction = <<-EOT
        You are an expert software architect. Analyze the provided list of filenames and infer the project's purpose, main language, and potential frameworks.
        Base your answer on file extensions and common project files. Output only a single paragraph.
      EOT
      # No action group needed
    }
    installation_guide = {
      name        = "ed45-Installation_Guide_Agent"
      instruction = <<-EOT
        You are a technical writer. Examine the list of filenames and identify any dependency management files.
        If found, write a '## Installation' section in Markdown with the appropriate command.
        If none, respond exactly with: 'No dependency management file found.'
      EOT
    }
    usage_examples = {
      name        = "ed45-Usage_Examples_Agent"
      instruction = <<-EOT
        You are a developer advocate. Look at the filenames and determine the most likely main entry point.
        Provide a '## Usage' section in Markdown showing a typical command to run the project.
        If you cannot identify an entry point, respond with: 'Could not determine a main script.'
      EOT
    }
  }
}


