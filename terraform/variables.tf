variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "cloudwatch-logs-s3-exporter"
}

variable "environment" {
  description = "Environment name (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for exported logs (must be globally unique)"
  type        = string
}

variable "days_threshold" {
  description = "Number of days old before logs are exported to S3"
  type        = number
  default     = 3
  
  validation {
    condition     = var.days_threshold >= 1 && var.days_threshold <= 365
    error_message = "Days threshold must be between 1 and 365."
  }
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 900
  
  validation {
    condition     = var.lambda_timeout >= 1 && var.lambda_timeout <= 900
    error_message = "Lambda timeout must be between 1 and 900 seconds."
  }
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 256
  
  validation {
    condition     = var.lambda_memory_size >= 128 && var.lambda_memory_size <= 10240
    error_message = "Lambda memory size must be between 128 and 10240 MB."
  }
}

variable "enable_schedule" {
  description = "Enable EventBridge rule for scheduled execution"
  type        = bool
  default     = true
}

variable "schedule_expression" {
  description = "Cron expression for EventBridge rule (runs daily at 2 AM UTC by default)"
  type        = string
  default     = "cron(0 2 * * ? *)"
}

variable "s3_lifecycle_enabled" {
  description = "Enable S3 lifecycle policies for cost optimization"
  type        = bool
  default     = true
}

variable "s3_transition_to_ia_days" {
  description = "Number of days before transitioning to Standard-IA storage class"
  type        = number
  default     = 30
}

variable "s3_transition_to_glacier_days" {
  description = "Number of days before transitioning to Glacier storage class"
  type        = number
  default     = 90
}

variable "s3_expiration_days" {
  description = "Number of days before objects expire (0 = never expire)"
  type        = number
  default     = 2555  # 7 years
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days for Lambda function logs"
  type        = number
  default     = 14
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}