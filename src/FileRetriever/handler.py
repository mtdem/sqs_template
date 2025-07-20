import json
import boto3
import os
import sys
from botocore.exceptions import ClientError
import logging
from typing import List, Dict, Any

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')

# Constants
S3_BUCKET = "test-jbry"
S3_FOLDER = "Source"
MAX_BATCH_SIZE_BYTES = 256 * 1024  # 256KB
MAX_SQS_BATCH_SIZE = 10  # Maximum 10 messages per batch

def get_queue_url():
    """Get the SQS queue URL from environment variables"""
    queue_url = os.environ.get('FILEUPLOADMANAGERQUEUE_QUEUE_URL')
    if not queue_url:
        raise ValueError("FILEUPLOADMANAGERQUEUE_QUEUE_URL environment variable not set")
    return queue_url

def list_s3_files(bucket: str, folder: str) -> List[str]:
    """
    List all files in the specified S3 bucket and folder
    """
    logger.info(f"Listing files in s3://{bucket}/{folder}")
    
    file_names = []
    paginator = s3_client.get_paginator('list_objects_v2')
    
    # Add trailing slash to folder if not present
    prefix = f"{folder}/" if folder and not folder.endswith('/') else folder
    
    try:
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    # Skip folder itself and only include files
                    if key != prefix and not key.endswith('/'):
                        # Extract just the filename (remove folder path)
                        file_name = key.replace(prefix, '')
                        if file_name:  # Ensure it's not empty
                            file_names.append(file_name)
        
        logger.info(f"Found {len(file_names)} files in s3://{bucket}/{folder}")
        return file_names
        
    except ClientError as e:
        logger.error(f"Error listing S3 files: {e}")
        raise

def build_document_collection(file_names: List[str], bucket: str, folder: str) -> List[Dict[str, str]]:
    """
    Build a collection of Document objects from file names
    """
    documents = []
    
    for file_name in file_names:
        document = {
            's3_bucket': bucket,
            's3_folder': folder,
            'file_name': file_name
        }
        documents.append(document)
    
    logger.info(f"Built {len(documents)} Document objects")
    return documents

def calculate_message_size(documents: List[Dict[str, str]]) -> int:
    """
    Calculate the size of a document collection when serialized to JSON
    """
    return len(json.dumps(documents).encode('utf-8'))

def split_documents_into_batches(documents: List[Dict[str, str]], max_size_bytes: int) -> List[List[Dict[str, str]]]:
    """
    Split document collection into batches that don't exceed the specified size limit
    """
    batches = []
    current_batch = []
    
    for document in documents:
        # Create a test batch with the new document
        test_batch = current_batch + [document]
        
        # Check if adding this document would exceed the size limit
        if calculate_message_size(test_batch) > max_size_bytes:
            # If current batch is not empty, save it and start a new one
            if current_batch:
                batches.append(current_batch)
                current_batch = [document]
            else:
                # If single document exceeds limit, still include it (edge case)
                logger.warning(f"Single document exceeds size limit: {document}")
                batches.append([document])
                current_batch = []
        else:
            current_batch = test_batch
    
    # Add the last batch if it's not empty
    if current_batch:
        batches.append(current_batch)
    
    logger.info(f"Split {len(documents)} documents into {len(batches)} batches")
    return batches

def send_sqs_messages(document_batches: List[List[Dict[str, str]]], queue_url: str) -> int:
    """
    Send document batches to SQS queue, processing maximum 10 messages at a time
    """
    total_sent = 0
    
    # Process batches in chunks of 10 (SQS send_message_batch limit)
    for i in range(0, len(document_batches), MAX_SQS_BATCH_SIZE):
        batch_chunk = document_batches[i:i + MAX_SQS_BATCH_SIZE]
        
        # Prepare entries for send_message_batch
        entries = []
        for j, documents in enumerate(batch_chunk):
            entry = {
                'Id': str(i + j),
                'MessageBody': json.dumps(documents)
            }
            entries.append(entry)
        
        try:
            logger.info(f"Sending batch of {len(entries)} messages to SQS")
            response = sqs_client.send_message_batch(
                QueueUrl=queue_url,
                Entries=entries
            )
            
            successful = len(response.get('Successful', []))
            failed = len(response.get('Failed', []))
            
            logger.info(f"Successfully sent {successful} messages, {failed} failed")
            
            if failed > 0:
                for failure in response.get('Failed', []):
                    logger.error(f"Failed to send message {failure['Id']}: {failure['Message']}")
            
            total_sent += successful
            
        except ClientError as e:
            logger.error(f"Error sending SQS messages: {e}")
            raise
    
    return total_sent

def handler(event, context):
    """
    Main lambda handler - retrieves files from S3, builds Document collection, 
    and sends batched messages to SQS
    """
    logger.info(f"FileRetriever started. Event: {json.dumps(event)}")
    
    try:
        # Get SQS queue URL
        queue_url = get_queue_url()
        
        # Step 1: List all files in S3 bucket and folder
        file_names = list_s3_files(S3_BUCKET, S3_FOLDER)
        
        if not file_names:
            logger.info("No files found in S3 bucket/folder")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No files found to process',
                    'filesFound': 0,
                    'messagesSpent': 0
                })
            }
        
        # Step 2: Build Document collection
        documents = build_document_collection(file_names, S3_BUCKET, S3_FOLDER)
        
        # Step 3: Split into batches based on size limit
        document_batches = split_documents_into_batches(documents, MAX_BATCH_SIZE_BYTES)
        
        # Step 4: Send batches to SQS (max 10 at a time)
        messages_sent = send_sqs_messages(document_batches, queue_url)
        
        logger.info(f"Processing completed. Files: {len(file_names)}, Messages sent: {messages_sent}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'File retrieval and messaging completed successfully',
                'filesFound': len(file_names),
                'documentsCreated': len(documents),
                'batchesCreated': len(document_batches),
                'messagesSent': messages_sent
            })
        }
        
    except Exception as e:
        logger.error(f"Error in FileRetriever handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Error processing file retrieval',
                'error': str(e)
            })
        }