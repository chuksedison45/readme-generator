output "repo_scanner_lambda_arn" {
  description = "ARN of the Repo Scanner Lambda function."
  value       = aws_lambda_function.repo_scanner_lambda.arn
}

output "repo_scanner_agent_id" {
  description = "ID of the Repo Scanner Bedrock Agent."
  value       = module.all_agents["repo_scanner"].agent_id
}

output "repo_scanner_agent_arn" {
  description = "ARN of the Repo Scanner Bedrock Agent."
  value       = module.all_agents["repo_scanner"].agent_arn
}

output "project_summarizer_agent_id" {
  description = "ID of the Project Summarizer Bedrock Agent."
  value       = module.all_agents["project_summarizer"].agent_id
}

output "installation_guide_agent_id" {
  description = "ID of the Installation Guide Bedrock Agent."
  value       = module.all_agents["installation_guide"].agent_id
}

output "usage_examples_agent_id" {
  description = "ID of the Usage Examples Bedrock Agent."
  value       = module.all_agents["usage_examples"].agent_id
}

output "bedrock_agent_role_arn" {
  description = "ARN of the IAM role used by Bedrock Agents."
  value       = module.bedrock_agent_role.role_arn
}
