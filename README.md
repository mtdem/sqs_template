# S3 to SQS File Processor Lambda

This AWS Lambda function processes files from an S3 bucket and sends their metadata to an SQS queue in optimally-sized batches.

## Overview

The Lambda function performs the following steps:

1. **Extract file paths** from a specified S3 bucket and folder using `s3fileextractor.py`
2. **Transform file paths** into Document JSON objects using `s3filetransformer.py`
3. **Split Documents** into SQS-compatible message batches (max 250KB per message) using `s3messagebatchhandler.py`
4. **Send messages** to SQS queue one at a time using `sqsservice.py`

## Project Structure

```
├── lambda_function.py              # Main Lambda handler
├── s3fileextractor.py             # S3 file path extraction
├── s3filetransformer.py          # File path to Document transformation
├── s3messagebatchhandler.py      # Document batching for SQS
├── sqsservice.py                 # SQS message sending
├── requirements.txt              # Python dependencies
├── serverless.yml               # Serverless Framework deployment config
└── README.md                   # This documentation
```

## Requirements

- Python 3.9+
- AWS CLI configured with appropriate credentials
- Serverless Framework (optional, for deployment)

## Dependencies

The project uses these main dependencies (see `requirements.txt`):

- `boto3` - AWS SDK for Python
- `botocore` - Low-level AWS service access
- `typing-extensions` - Enhanced type hints

## Setup and Deployment

### Option 1: Serverless Framework (Recommended)

1. Install Serverless Framework:
   ```bash
   npm install -g serverless
   npm install serverless-python-requirements
   ```

2. Deploy the function:
   ```bash
   serverless deploy
   ```

3. Deploy to specific stage/region:
   ```bash
   serverless deploy --stage prod --region us-west-2
   ```

### Option 2: Manual Deployment

1. Install dependencies:
   ```bash
   pip install -r requirements.txt -t .
   ```

2. Create deployment package:
   ```bash
   zip -r lambda-deployment.zip . -x "*.git*" "*.md" "__pycache__/*" "*.pyc"
   ```

3. Upload to AWS Lambda console or use AWS CLI:
   ```bash
   aws lambda create-function \
     --function-name s3-to-sqs-processor \
     --runtime python3.9 \
     --role arn:aws:iam::ACCOUNT:role/lambda-execution-role \
     --handler lambda_function.lambda_handler \
     --zip-file fileb://lambda-deployment.zip
   ```

## Usage

### Lambda Event Format

The Lambda function expects an event with the following structure:

```json
{
  "bucket_name": "my-s3-bucket",
  "folder_key": "documents/",
  "queue_name": "my-sqs-queue",
  "region_name": "us-east-1",
  "delay_between_messages": 0.1
}
```

#### Required Parameters

- `bucket_name` (string): Name of the S3 bucket to process
- `queue_name` (string): Name of the target SQS queue

#### Optional Parameters

- `folder_key` (string): S3 folder/prefix to filter files (default: "")
- `region_name` (string): AWS region (default: "us-east-1")
- `delay_between_messages` (float): Delay between message sends in seconds (default: 0.1)

### Example Invocation

#### Using AWS CLI

```bash
aws lambda invoke \
  --function-name s3-to-sqs-processor \
  --payload '{
    "bucket_name": "my-documents-bucket",
    "folder_key": "invoices/2024/",
    "queue_name": "document-processing-queue",
    "region_name": "us-east-1"
  }' \
  response.json
```

#### Using Serverless Framework

```bash
serverless invoke -f processS3Files --data '{
  "bucket_name": "my-documents-bucket",
  "folder_key": "invoices/2024/",
  "queue_name": "document-processing-queue"
}'
```

### Response Format

The Lambda function returns a JSON response with execution details:

```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "message": "Lambda execution completed successfully",
    "files_found": 150,
    "documents_created": 150,
    "messages_created": 3,
    "messages_sent": 3,
    "total_payload_size_bytes": 524288,
    "average_message_size_bytes": 174762.67,
    "execution_details": {
      "bucket_name": "my-documents-bucket",
      "folder_key": "invoices/2024/",
      "queue_name": "document-processing-queue",
      "region_name": "us-east-1"
    }
  }
}
```

## Document Structure

Each file path is transformed into a Document object with this structure:

```json
{
  "file_path": "documents/invoice_2024_001.pdf",
  "file_name": "invoice_2024_001.pdf",
  "file_extension": "pdf",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

## SQS Message Structure

Documents are batched into SQS messages with this structure:

```json
{
  "message_id": "batch_1",
  "document_count": 50,
  "documents": [
    {
      "file_path": "documents/file1.pdf",
      "file_name": "file1.pdf",
      "file_extension": "pdf",
      "timestamp": "2024-01-15T10:30:00.000Z"
    }
  ]
}
```

## IAM Permissions

The Lambda execution role needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:GetQueueUrl",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:region:account:queue-name"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## Configuration

### Lambda Configuration

- **Runtime**: Python 3.9
- **Memory**: 512 MB (adjustable based on file volume)
- **Timeout**: 15 minutes (adjustable based on processing needs)
- **Architecture**: x86_64

### SQS Considerations

- The function sends messages to **standard SQS queues**
- Each message is limited to 250KB (with 6KB buffer below AWS 256KB limit)
- Messages are sent sequentially with configurable delays
- Dead letter queues are recommended for error handling

## Monitoring and Logging

The function provides comprehensive logging including:

- File extraction progress
- Document transformation statistics
- Message batching details
- SQS sending results
- Error handling and retries

Monitor these CloudWatch metrics:
- Lambda duration and memory usage
- SQS message counts and errors
- S3 API call frequency

## Error Handling

The function handles various error scenarios:

- **S3 Access Errors**: Bucket not found, access denied
- **SQS Errors**: Queue not found, message size limits
- **Validation Errors**: Missing required parameters
- **Processing Errors**: Document transformation failures

All errors are logged with appropriate context for debugging.

## Local Testing

To test locally:

1. Configure AWS credentials
2. Run the test script:
   ```bash
   python lambda_function.py
   ```

3. Uncomment the test invocation in `__main__` section for actual testing

## Best Practices

1. **S3 Bucket Organization**: Use clear folder structures for efficient processing
2. **SQS Queue Configuration**: Set appropriate visibility timeouts and dead letter queues
3. **Lambda Memory**: Adjust based on file volume and processing requirements
4. **Error Handling**: Monitor CloudWatch logs and set up alarms
5. **Cost Optimization**: Use S3 lifecycle policies and SQS message lifecycle management

## Troubleshooting

### Common Issues

1. **No files found**: Check bucket name and folder key
2. **Access denied**: Verify IAM permissions for S3 and SQS
3. **Message too large**: Individual documents may be too large for SQS
4. **Timeout errors**: Increase Lambda timeout or reduce batch sizes

### Debug Mode

Enable debug logging by setting the Lambda environment variable:
```
LOG_LEVEL=DEBUG
```

## Contributing

When modifying the code:

1. Update type hints and documentation
2. Add appropriate error handling
3. Update tests and validation
4. Follow Python PEP 8 style guidelines

## License

This project is provided as-is for educational and development purposes. 