# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# S3 Bucket for storing exported logs
resource "aws_s3_bucket" "logs_bucket" {
  bucket = var.s3_bucket_name
}

resource "aws_s3_bucket_versioning" "logs_bucket_versioning" {
  bucket = aws_s3_bucket.logs_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs_bucket_encryption" {
  bucket = aws_s3_bucket.logs_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "logs_bucket_pab" {
  bucket = aws_s3_bucket.logs_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "logs_bucket_lifecycle" {
  count = var.s3_lifecycle_enabled ? 1 : 0
  
  bucket = aws_s3_bucket.logs_bucket.id

  rule {
    id     = "log_retention_policy"
    status = "Enabled"

    transition {
      days          = var.s3_transition_to_ia_days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = var.s3_transition_to_glacier_days
      storage_class = "GLACIER"
    }

    dynamic "expiration" {
      for_each = var.s3_expiration_days > 0 ? [1] : []
      content {
        days = var.s3_expiration_days
      }
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-${var.environment}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for CloudWatch Logs operations
resource "aws_iam_policy" "lambda_logs_policy" {
  name        = "${var.project_name}-${var.environment}-logs-policy"
  description = "IAM policy for CloudWatch Logs operations"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:CreateExportTask",
          "logs:DescribeExportTasks"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Policy for S3 operations
resource "aws_iam_policy" "lambda_s3_policy" {
  name        = "${var.project_name}-${var.environment}-s3-policy"
  description = "IAM policy for S3 operations"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetBucketLocation",
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.logs_bucket.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${aws_s3_bucket.logs_bucket.arn}/*"
      }
    ]
  })
}

# Attach policies to Lambda execution role
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_logs_policy_attachment" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_logs_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_s3_policy_attachment" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_s3_policy.arn
}

# CloudWatch Log Group for Lambda function
resource "aws_cloudwatch_log_group" "lambda_log_group" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days
}

# Create deployment package
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../src/lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}

# Lambda Function
resource "aws_lambda_function" "cloudwatch_logs_exporter" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${var.project_name}-${var.environment}"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.9"
  timeout         = var.lambda_timeout
  memory_size     = var.lambda_memory_size

  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.logs_bucket.bucket
      DAYS_THRESHOLD = var.days_threshold
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy_attachment.lambda_logs_policy_attachment,
    aws_iam_role_policy_attachment.lambda_s3_policy_attachment,
    aws_cloudwatch_log_group.lambda_log_group,
  ]
}

# EventBridge Rule for scheduled execution (optional)
resource "aws_cloudwatch_event_rule" "schedule_rule" {
  count = var.enable_schedule ? 1 : 0
  
  name                = "${var.project_name}-${var.environment}-schedule"
  description         = "Trigger CloudWatch logs export"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  count = var.enable_schedule ? 1 : 0
  
  rule      = aws_cloudwatch_event_rule.schedule_rule[0].name
  target_id = "CloudWatchLogsExporterTarget"
  arn       = aws_lambda_function.cloudwatch_logs_exporter.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  count = var.enable_schedule ? 1 : 0
  
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cloudwatch_logs_exporter.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule_rule[0].arn
}