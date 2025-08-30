"""
CloudWatch Logs to S3 Exporter

AWS Lambda function that automatically exports CloudWatch log groups' logs
(older than specified threshold) to S3 buckets with organized folder structure.

"""

import json
import boto3
import datetime
import os
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError
import logging

# Configure logging
logger = logging.getLogger()
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logger.setLevel(getattr(logging, log_level, logging.INFO))


class CloudWatchLogsToS3Exporter:
    """
    A class to handle exporting CloudWatch logs to S3.
    
    This class provides methods to:
    - Discover log groups and streams
    - Filter logs based on age threshold
    - Create export tasks to S3
    - Handle errors and provide detailed logging
    """
    
    def __init__(self) -> None:
        """Initialize the exporter with AWS clients and configuration."""
        self.logs_client = boto3.client('logs')
        self.s3_client = boto3.client('s3')
        self.s3_bucket = os.environ.get('S3_BUCKET_NAME')
        self.days_threshold = int(os.environ.get('DAYS_THRESHOLD', '3'))
        
        if not self.s3_bucket:
            raise ValueError("S3_BUCKET_NAME environment variable is required")
        
        logger.info(f"Initialized exporter with bucket: {self.s3_bucket}, "
                   f"threshold: {self.days_threshold} days")
    
    def get_log_groups(self, log_group_names: Optional[List[str]] = None) -> List[str]:
        """
        Get log groups to process.
        
        Args:
            log_group_names: Optional list of specific log group names.
                           If None, returns all available log groups.
        
        Returns:
            List of valid log group names.
        """
        if log_group_names:
            valid_groups = []
            for group_name in log_group_names:
                try:
                    response = self.logs_client.describe_log_groups(
                        logGroupNamePrefix=group_name,
                        limit=1
                    )
                    if response['logGroups']:
                        # Verify exact match
                        for group in response['logGroups']:
                            if group['logGroupName'] == group_name:
                                valid_groups.append(group_name)
                                break
                        else:
                            logger.warning(f"Exact match not found for log group: {group_name}")
                    else:
                        logger.warning(f"Log group not found: {group_name}")
                except ClientError as e:
                    logger.error(f"Error checking log group {group_name}: {e}")
            
            logger.info(f"Found {len(valid_groups)} valid log groups from specified list")
            return valid_groups
        
        # Get all log groups
        log_groups = []
        try:
            paginator = self.logs_client.get_paginator('describe_log_groups')
            
            for page in paginator.paginate():
                for log_group in page['logGroups']:
                    log_groups.append(log_group['logGroupName'])
            
            logger.info(f"Found {len(log_groups)} total log groups")
        except ClientError as e:
            logger.error(f"Error listing log groups: {e}")
            return []
        
        return log_groups
    
    def get_log_streams_to_export(self, log_group_name: str) -> List[Dict[str, Any]]:
        """
        Get log streams that are older than the threshold days.
        
        Args:
            log_group_name: Name of the log group to check.
        
        Returns:
            List of dictionaries containing stream information.
        """
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=self.days_threshold)
        cutoff_timestamp = int(cutoff_time.timestamp() * 1000)  # Convert to milliseconds
        
        logger.debug(f"Cutoff timestamp for {log_group_name}: {cutoff_timestamp} "
                    f"({cutoff_time.isoformat()})")
        
        streams_to_export = []
        try:
            paginator = self.logs_client.get_paginator('describe_log_streams')
            
            for page in paginator.paginate(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=False  # Get oldest first
            ):
                for stream in page['logStreams']:
                    last_event_time = stream.get('lastEventTime', 0)
                    
                    if last_event_time < cutoff_timestamp:
                        streams_to_export.append({
                            'logStreamName': stream['logStreamName'],
                            'lastEventTime': last_event_time,
                            'creationTime': stream.get('creationTime', 0),
                            'lastIngestionTime': stream.get('lastIngestionTime', 0)
                        })
                    else:
                        # Since we're ordering by LastEventTime ascending,
                        # we can break early once we hit newer streams
                        break
        except ClientError as e:
            logger.error(f"Error getting log streams for {log_group_name}: {e}")
            return []
        
        logger.info(f"Found {len(streams_to_export)} old streams in {log_group_name}")
        return streams_to_export
    
    def _generate_s3_prefix(self, log_group_name: str) -> str:
        """
        Generate S3 key prefix (folder structure) for a log group.
        
        Args:
            log_group_name: Original log group name.
        
        Returns:
            Safe S3 prefix string.
        """
        # Remove leading slash and replace special characters
        safe_name = log_group_name.lstrip('/').replace('/', '_').replace(' ', '_')
        # Remove any other problematic characters
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c in '-_.')
        
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        return f"{safe_name}/{timestamp}"
    
    def create_export_task(self, log_group_name: str, streams: List[Dict[str, Any]]) -> Optional[str]:
        """
        Create an export task for the specified log group and streams.
        
        Args:
            log_group_name: Name of the log group to export.
            streams: List of stream dictionaries to export.
        
        Returns:
            Task ID if successful, None otherwise.
        """
        if not streams:
            logger.info(f"No streams to export for log group: {log_group_name}")
            return None
        
        # Calculate time range for export
        start_time = min(stream['creationTime'] for stream in streams if stream['creationTime'] > 0)
        end_time = max(stream['lastEventTime'] for stream in streams if stream['lastEventTime'] > 0)
        
        if start_time == 0 or end_time == 0:
            logger.warning(f"Invalid time range for {log_group_name}, skipping export")
            return None
        
        # Generate S3 key prefix
        s3_prefix = self._generate_s3_prefix(log_group_name)
        
        try:
            response = self.logs_client.create_export_task(
                logGroupName=log_group_name,
                fromTime=start_time,
                to=end_time,
                destination=self.s3_bucket,
                destinationPrefix=s3_prefix
            )
            
            task_id = response['taskId']
            logger.info(f"✅ Created export task {task_id} for {log_group_name}")
            logger.info(f"📁 Destination: s3://{self.s3_bucket}/{s3_prefix}")
            logger.info(f"📊 Exporting {len(streams)} streams")
            
            return task_id
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'LimitExceededException':
                logger.warning(f"⚠️  Export task limit exceeded for {log_group_name}. "
                             "Will retry in next execution.")
            elif error_code == 'ResourceAlreadyExistsException':
                logger.warning(f"⚠️  Export task already exists for {log_group_name}")
            elif error_code == 'InvalidParameterException':
                logger.error(f"❌ Invalid parameters for {log_group_name}: {e}")
            else:
                logger.error(f"❌ Error creating export task for {log_group_name}: {e}")
            
            return None
    
    def check_export_task_status(self, task_id: str) -> str:
        """
        Check the status of an export task.
        
        Args:
            task_id: The export task ID.
        
        Returns:
            Status string: RUNNING, COMPLETED, FAILED, CANCELLED, or UNKNOWN.
        """
        try:
            response = self.logs_client.describe_export_tasks(taskId=task_id)
            if response['exportTasks']:
                status = response['exportTasks'][0]['status']['code']
                logger.debug(f"Export task {task_id} status: {status}")
                return status
        except ClientError as e:
            logger.error(f"Error checking export task {task_id}: {e}")
        
        return "UNKNOWN"
    
    def process_log_groups(self, log_group_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Main method to process log groups and create export tasks.
        
        Args:
            log_group_names: Optional list of specific log group names to process.
        
        Returns:
            Dictionary containing processing results and statistics.
        """
        start_time = datetime.datetime.now()
        
        results = {
            'processed_log_groups': 0,
            'created_export_tasks': 0,
            'skipped_log_groups': 0,
            'export_tasks': [],
            'errors': [],
            'start_time': start_time.isoformat(),
            'total_streams_processed': 0
        }
        
        log_groups = self.get_log_groups(log_group_names)
        
        if not log_groups:
            logger.warning("No log groups found to process")
            return results
        
        logger.info(f"🚀 Starting processing of {len(log_groups)} log groups")
        
        for i, log_group_name in enumerate(log_groups, 1):
            try:
                logger.info(f"📋 Processing log group {i}/{len(log_groups)}: {log_group_name}")
                
                # Get streams older than threshold
                streams_to_export = self.get_log_streams_to_export(log_group_name)
                results['total_streams_processed'] += len(streams_to_export)
                
                if not streams_to_export:
                    logger.info(f"⏭️  No old streams found in {log_group_name}")
                    results['skipped_log_groups'] += 1
                    results['processed_log_groups'] += 1
                    continue
                
                # Create export task
                task_id = self.create_export_task(log_group_name, streams_to_export)
                
                if task_id:
                    results['created_export_tasks'] += 1
                    results['export_tasks'].append({
                        'taskId': task_id,
                        'logGroupName': log_group_name,
                        'streamsCount': len(streams_to_export),
                        'status': 'RUNNING'
                    })
                else:
                    results['skipped_log_groups'] += 1
                
                results['processed_log_groups'] += 1
                
            except Exception as e:
                error_msg = f"Error processing log group {log_group_name}: {str(e)}"
                logger.error(f"❌ {error_msg}")
                results['errors'].append(error_msg)
        
        # Calculate processing duration
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        results['end_time'] = end_time.isoformat()
        results['duration_seconds'] = duration
        
        # Log summary
        logger.info(f"✨ Processing completed in {duration:.2f} seconds")
        logger.info(f"📊 Summary: {results['processed_log_groups']} processed, "
                   f"{results['created_export_tasks']} exported, "
                   f"{results['skipped_log_groups']} skipped, "
                   f"{len(results['errors'])} errors")
        
        return results


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function.
    
    Event structure options:
    1. Process all log groups: {}
    2. Process specific log groups: {"log_groups": ["/aws/lambda/func1", "/aws/lambda/func2"]}
    3. Process single log group: {"log_group": "/aws/lambda/my-function"}
    
    Args:
        event: Lambda event data.
        context: Lambda context object.
    
    Returns:
        Response dictionary with status and results.
    """
    
    # Log the incoming event (excluding sensitive data)
    safe_event = {k: v for k, v in event.items() if k not in ['password', 'secret', 'token']}
    logger.info(f"Received event: {json.dumps(safe_event)}")
    
    try:
        # Initialize the exporter
        exporter = CloudWatchLogsToS3Exporter()
        
        # Parse input parameters
        log_group_names = None
        
        if 'log_groups' in event:
            log_group_names = event['log_groups']
            if not isinstance(log_group_names, list):
                raise ValueError("'log_groups' must be a list of strings")
            logger.info(f"Processing specific log groups: {log_group_names}")
            
        elif 'log_group' in event:
            log_group_names = [event['log_group']]
            logger.info(f"Processing single log group: {event['log_group']}")
        else:
            logger.info("Processing all available log groups")
        
        # Process log groups
        results = exporter.process_log_groups(log_group_names)
        
        # Prepare response
        response = {
            'statusCode': 200,
            'body': {
                'message': 'CloudWatch logs export process completed successfully',
                'results': results,
                'configuration': {
                    's3_bucket': exporter.s3_bucket,
                    'days_threshold': exporter.days_threshold,
                    'function_name': context.function_name,
                    'aws_request_id': context.aws_request_id
                }
            }
        }
        
        logger.info("🎉 Lambda execution completed successfully")
        return response
        
    except Exception as e:
        error_msg = f"Lambda execution failed: {str(e)}"
        logger.error(f"💥 {error_msg}", exc_info=True)
        
        return {
            'statusCode': 500,
            'body': {
                'error': error_msg,
                'error_type': type(e).__name__,
                'aws_request_id': context.aws_request_id if context else 'unknown'
            }
        }


# For local testing and development
if __name__ == "__main__":
    import sys
    
    # Test event examples
    test_events = {
        'all': {},
        'specific': {
            "log_groups": ["/aws/lambda/test-function", "/aws/apigateway/test-api"]
        },
        'single': {
            "log_group": "/aws/lambda/test-function"
        }
    }
    
    # Mock context for testing
    class MockContext:
        def __init__(self):
            self.function_name = "cloudwatch-logs-s3-exporter-dev"
            self.memory_limit_in_mb = 256
            self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
            self.aws_request_id = "test-request-id-12345"
    
    # Choose test event
    test_type = sys.argv[1] if len(sys.argv) > 1 else 'single'
    test_event = test_events.get(test_type, test_events['single'])
    
    print(f"Testing with event type: {test_type}")
    print(f"Event: {json.dumps(test_event, indent=2)}")
    print("-" * 50)
    
    # Test the function
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2, default=str))