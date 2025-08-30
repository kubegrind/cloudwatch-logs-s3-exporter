output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.cloudwatch_logs_exporter.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.cloudwatch_logs_exporter.function_name
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for exported logs"
  value       = aws_s3_bucket.logs_bucket.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.logs_bucket.arn
}

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution_role.arn
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge rule (if enabled)"
  value       = var.enable_schedule ? aws_cloudwatch_event_rule.schedule_rule[0].arn : null
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for Lambda function"
  value       = aws_cloudwatch_log_group.lambda_log_group.name
}

output "deployment_region" {
  description = "AWS region where resources are deployed"
  value       = data.aws_region.current.name
}

output "account_id" {
  description = "AWS account ID where resources are deployed"
  value       = data.aws_caller_identity.current.account_id
}

output "invoke_command" {
  description = "AWS CLI command to invoke the Lambda function"
  value       = "aws lambda invoke --function-name ${aws_lambda_function.cloudwatch_logs_exporter.function_name} --payload '{}' response.json"
}