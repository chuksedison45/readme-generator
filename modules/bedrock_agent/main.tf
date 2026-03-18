resource "aws_bedrockagent_agent" "this" {
  agent_name              = var.agent_name
  foundation_model        = var.foundation_model
  instruction             = var.instruction
  agent_resource_role_arn = var.agent_resource_role_arn
}

resource "aws_bedrockagent_agent_action_group" "this" {
  count = var.action_group_uri != null ? 1 : 0

  agent_id           = aws_bedrockagent_agent.this.agent_id
  agent_version      = "DRAFT"
  action_group_name  = "ED45-ScanRepoAction"
  action_group_state = "ENABLED"
  description        = "Tool to scan a GitHub repository"
  action_group_executor {
    lambda = var.action_group_uri
  }

  api_schema {
    payload = file("${path.root}/repo_scanner_schema.json")
  }
}
