#!/usr/bin/env python3

import os
import sys
import json
from unittest.mock import MagicMock

# Add the FileRetriever directory to the path so we can import the handler
sys.path.append('src/FileRetriever')

# Import the handler
from handler import handler

def main():
    """
    Test the FileRetriever handler locally
    """
    
    # Set environment variables if not already set
    if not os.environ.get('FILEUPLOADMANAGERQUEUE_QUEUE_URL'):
        # You need to replace this with your actual queue URL
        # Get it from AWS Console or CLI: aws sqs get-queue-url --queue-name YourQueueName
        queue_url = input("Enter your SQS Queue URL: ").strip()
        if not queue_url:
            print("Error: Queue URL is required")
            return
        os.environ['FILEUPLOADMANAGERQUEUE_QUEUE_URL'] = queue_url
    
    # Create a mock Lambda event (empty for this handler since it doesn't use the event)
    test_event = {}
    
    # Create a mock Lambda context
    context = MagicMock()
    context.aws_request_id = "test-request-id"
    context.function_name = "FileRetriever"
    context.function_version = "$LATEST"
    context.memory_limit_in_mb = 3008
    context.remaining_time_in_millis = lambda: 300000  # 5 minutes
    
    print("Starting FileRetriever handler test...")
    print(f"Queue URL: {os.environ.get('FILEUPLOADMANAGERQUEUE_QUEUE_URL')}")
    print(f"S3 Bucket: test-jbry")
    print(f"S3 Folder: Source")
    print("-" * 50)
    
    try:
        # Call the handler
        response = handler(test_event, context)
        
        print("Handler execution completed!")
        print(f"Status Code: {response['statusCode']}")
        
        # Parse and display the response body
        body = json.loads(response['body'])
        print(f"Message: {body['message']}")
        
        if 'filesFound' in body:
            print(f"Files Found: {body['filesFound']}")
        if 'documentsCreated' in body:
            print(f"Documents Created: {body['documentsCreated']}")
        if 'batchesCreated' in body:
            print(f"Batches Created: {body['batchesCreated']}")
        if 'messagesSent' in body:
            print(f"Messages Sent: {body['messagesSent']}")
            
    except Exception as e:
        print(f"Error running handler: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()