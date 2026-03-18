terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "aws" {
  region = "us-east-1" # You can change this to your preferred region
}

resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# ----------------------------------------------------------------------
# S3 bucket for storing generated READMEs (optional)
# ----------------------------------------------------------------------
module "s3_bucket" {
  source      = "./modules/s3"
  bucket_name = "ed45-readme-generator-output-bucket-${random_string.suffix.result}"
}


# Role specifically for the Lambda function to run
module "lambda_execution_role" {
  source             = "./modules/iam"
  role_name          = "ed45-ReadmeGeneratorLambdaExecutionRole"
  service_principals = ["lambda.amazonaws.com"]
  policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  ]
}

# ----------------------------------------------------------------------
# IAM role for Bedrock Agents (assumed by the agents)
# ----------------------------------------------------------------------
# Role specifically for the Bedrock Agent to use
module "bedrock_agent_role" {
  source             = "./modules/iam"
  role_name          = "ed45-ReadmeGeneratorBedrockAgentRole"
  service_principals = ["bedrock.amazonaws.com"]
  policy_arns = [
    "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
  ]
}

output "readme_bucket_name" {
  description = "The name of the S3 bucket where README files are stored."
  value       = module.s3_bucket.bucket_id
}


data "archive_file" "repo_scanner_zip" {
  type        = "zip"
  source_dir  = "${path.root}/src/repo_scanner"
  output_path = "${path.root}/dist/repo_scanner.zip"
}

# ----------------------------------------------------------------------
# Lambda function for the Repo Scanner tool
# ----------------------------------------------------------------------
resource "aws_lambda_function" "repo_scanner_lambda" {
  function_name    = "ed45-RepoScannerTool"
  role             = module.lambda_execution_role.role_arn # Uses the dedicated Lambda role
  filename         = data.archive_file.repo_scanner_zip.output_path
  handler          = "lambda_function.handler"
  runtime          = "python3.12"
  timeout          = 30 # Increased timeout for cloning
  source_code_hash = data.archive_file.repo_scanner_zip.output_base64sha256

  # This line adds the 'git' command to our Lambda environment
  layers = ["arn:aws:lambda:us-east-1:553035198032:layer:git-lambda2:8"]
}


module "all_agents" {
  source   = "./modules/bedrock_agent"
  for_each = local.agents

  agent_name              = each.value.name
  agent_resource_role_arn = module.bedrock_agent_role.role_arn
  instruction             = each.value.instruction
  action_group_uri        = try(each.value.action_group_uri, null)
}

# This resource grants the Bedrock Agent permission to invoke our Lambda function
resource "aws_lambda_permission" "allow_bedrock_to_invoke_lambda" {
  statement_id  = "AllowBedrockToInvokeRepoScannerLambda"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.repo_scanner_lambda.function_name
  principal     = "bedrock.amazonaws.com"
  source_arn    = module.all_agents["repo_scanner"].agent_arn
}


