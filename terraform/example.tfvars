# Project Configuration
project_name = "cloudwatch-logs-s3-exporter"
environment  = "dev"

# S3 Configuration
s3_bucket_name = "my-org-cloudwatch-logs-backup-dev"  # Must be globally unique

# Lambda Configuration
days_threshold      = 3
lambda_timeout      = 900
lambda_memory_size  = 256

# Scheduling Configuration
enable_schedule       = true
schedule_expression   = "cron(0 2 * * ? *)"  # Daily at 2 AM UTC

# S3 Lifecycle Configuration
s3_lifecycle_enabled         = true
s3_transition_to_ia_days     = 30
s3_transition_to_glacier_days = 90
s3_expiration_days           = 2555  # 7 years

# Monitoring Configuration
log_retention_days = 14

# Tags
tags = {
  Owner       = "DevOps Team"
  CostCenter  = "Engineering"
  Project     = "Log Management"
  Environment = "Development"
}