# CloudWatch Logs to S3 Exporter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Terraform](https://img.shields.io/badge/Terraform-v1.0+-blue.svg)](https://www.terraform.io/)
[![Python](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)
[![AWS](https://img.shields.io/badge/AWS-Lambda-orange.svg)](https://aws.amazon.com/lambda/)

A professional AWS Lambda function with Terraform infrastructure that automatically exports CloudWatch log groups to S3 with configurable retention policies and organized folder structures.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   EventBridge   │───▶│  Lambda Function │───▶│   S3 Bucket     │
│   (Schedule)    │    │   (Python 3.9)  │    │  (Log Storage)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  CloudWatch Logs │
                       │   (Log Groups)   │
                       └──────────────────┘

S3 Folder Structure:
s3://bucket/
├── aws_lambda_function-name/
│   └── 2024-08-30_18-30-00/
├── aws_apigateway_api-name/
│   └── 2024-08-30_18-30-00/
└── custom_application_logs/
    └── 2024-08-30_18-30-00/
```

## ✨ Features

- **🚀 Automated Export**: Automatically exports CloudWatch logs older than configurable threshold
- **📁 Organized Storage**: Creates S3 folder structure based on log group names
- **⚙️ Flexible Configuration**: Support for single/multiple log groups or all log groups
- **🔒 Security First**: Least privilege IAM policies and secure S3 bucket configuration
- **📊 Monitoring**: Comprehensive logging and error tracking
- **⏰ Scheduled Execution**: Optional EventBridge scheduling for automated runs
- **🏗️ Infrastructure as Code**: Complete Terraform configuration

## 🚀 Quick Start

### Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform >= 1.0
- Python 3.9+

### 1. Clone the Repository

```bash
git clone https://github.com/muhammadarslan-techsol/cloudwatch-logs-s3-exporter.git
cd cloudwatch-logs-s3-exporter
```

### 2. Configure Terraform Variables

```bash
cd terraform
cp example.tfvars terraform.tfvars
# Edit terraform.tfvars with your configuration
```

### 3. Deploy Infrastructure

```bash
terraform init
terraform plan
terraform apply
```

### 4. Test the Function

```bash
# Test with all log groups
aws lambda invoke \
  --function-name cloudwatch-logs-s3-exporter \
  --payload '{}' \
  response.json

# Test with specific log groups
aws lambda invoke \
  --function-name cloudwatch-logs-s3-exporter \
  --payload '{"log_groups": ["/aws/lambda/my-function"]}' \
  response.json
```

## ⚙️ Configuration

### Terraform Variables

| Variable | Description | Type | Default | Required |
|----------|-------------|------|---------|----------|
| `project_name` | Name prefix for all resources | `string` | `"cloudwatch-logs-s3-exporter"` | No |
| `environment` | Environment name (dev/staging/prod) | `string` | `"dev"` | No |
| `s3_bucket_name` | S3 bucket name for exported logs | `string` | `""` | Yes |
| `days_threshold` | Days old before logs are exported | `number` | `3` | No |
| `lambda_timeout` | Lambda timeout in seconds | `number` | `900` | No |
| `lambda_memory_size` | Lambda memory size in MB | `number` | `256` | No |
| `enable_schedule` | Enable EventBridge scheduling | `bool` | `true` | No |
| `schedule_expression` | Cron expression for scheduling | `string` | `"cron(0 2 * * ? *)"` | No |
| `tags` | Tags to apply to all resources | `map(string)` | `{}` | No |

### Lambda Event Formats

#### Process All Log Groups
```json
{}
```

#### Process Specific Log Groups
```json
{
  "log_groups": [
    "/aws/lambda/my-function-1",
    "/aws/lambda/my-function-2",
    "/aws/apigateway/my-api"
  ]
}
```

#### Process Single Log Group
```json
{
  "log_group": "/aws/lambda/my-function"
}
```

## 📊 Response Format

```json
{
  "statusCode": 200,
  "body": {
    "message": "CloudWatch logs export process completed",
    "results": {
      "processed_log_groups": 5,
      "created_export_tasks": 3,
      "skipped_log_groups": 2,
      "export_tasks": [
        {
          "taskId": "task-12345",
          "logGroupName": "/aws/lambda/my-function",
          "streamsCount": 10
        }
      ],
      "errors": []
    },
    "s3_bucket": "my-logs-bucket",
    "days_threshold": 3
  }
}
```

## 🔧 Advanced Configuration

### Custom IAM Policies

The Terraform configuration creates least-privilege IAM policies. To add custom permissions:

```hcl
# In terraform/main.tf, add to the Lambda execution role
resource "aws_iam_role_policy" "custom_policy" {
  name = "${var.project_name}-custom-policy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "your:custom:action"
        ]
        Resource = "*"
      }
    ]
  })
}
```

### S3 Lifecycle Policies

Customize S3 lifecycle rules in `terraform/main.tf`:

```hcl
lifecycle_rule {
  id      = "log_retention"
  enabled = true

  transition {
    days          = 30
    storage_class = "STANDARD_IA"
  }

  transition {
    days          = 90
    storage_class = "GLACIER"
  }

  expiration {
    days = 2555  # 7 years
  }
}
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Export Task Limit Exceeded
```
ERROR: Export task limit exceeded for /aws/lambda/my-function
```
**Solution**: AWS has limits on concurrent export tasks. The function handles this gracefully and will retry later.

#### 2. S3 Permission Denied
```
ERROR: AccessDenied when writing to S3 bucket
```
**Solution**: Verify S3 bucket policy and Lambda execution role permissions.

#### 3. Log Group Not Found
```
WARNING: Log group /aws/lambda/missing-function not found
```
**Solution**: Verify log group names exist or use wildcard patterns.

### Debugging

Enable detailed logging by setting the Lambda environment variable:

```bash
aws lambda update-function-configuration \
  --function-name cloudwatch-logs-s3-exporter \
  --environment Variables='{LOG_LEVEL=DEBUG}'
```

### Monitoring

Monitor the function through:

- **CloudWatch Logs**: `/aws/lambda/cloudwatch-logs-s3-exporter`
- **CloudWatch Metrics**: Lambda function metrics
- **S3 Access Logs**: Enable S3 access logging for audit trails

## 💰 Cost Optimization

### S3 Storage Classes

Configure appropriate storage classes based on access patterns:

- **Standard**: Frequently accessed logs (< 30 days)
- **Standard-IA**: Infrequently accessed logs (30-90 days)
- **Glacier**: Long-term archival (> 90 days)

### Lambda Optimization

- **Memory Size**: Start with 256MB, monitor and adjust
- **Timeout**: Set based on largest log group size
- **Execution Frequency**: Balance between cost and storage requirements

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📋 Requirements

### AWS Permissions

Minimum IAM permissions required for deployment:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:CreatePolicy",
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "s3:CreateBucket",
        "s3:PutBucketPolicy",
        "events:PutRule",
        "events:PutTargets"
      ],
      "Resource": "*"
    }
  ]
}
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- AWS Documentation for CloudWatch Logs Export API
- Terraform AWS Provider documentation
- Python boto3 library

## 📞 Support

If you encounter any issues or have questions:

1. Check the [Troubleshooting](#-troubleshooting) section
2. Search [existing issues](https://github.com/muhammadarslan-techsol/cloudwatch-logs-s3-exporter/issues)
3. Create a [new issue](https://github.com/muhammadarslan-techsol/cloudwatch-logs-s3-exporter/issues/new)

---

**Made with ❤️ by Kubegrind**