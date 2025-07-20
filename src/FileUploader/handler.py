import json
import boto3
from botocore.exceptions import ClientError
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
s3_client = boto3.client('s3')

def handler(event, context):
    """
    Process SQS messages containing a collection of Document objects and copy files to Destination folder
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    total_processed_documents = 0
    
    # Process each SQS record
    for record in event.get('Records', []):
        try:
            # Extract message body from SQS record
            message_body = record.get('body', '{}')
            logger.info(f"Processing message body: {message_body}")
            
            # Parse the collection of Document objects from message body
            documents = json.loads(message_body)
            
            # Ensure documents is a list/collection
            if not isinstance(documents, list):
                logger.error(f"Expected a list of documents, but got: {type(documents)}")
                continue
            
            logger.info(f"Processing {len(documents)} documents in this message")
            
            # Process each Document object in the collection
            for document in documents:
                try:
                    # Extract Document properties
                    s3_bucket = document.get('s3_bucket')
                    s3_folder = document.get('s3_folder')
                    file_name = document.get('file_name')
                    
                    # Validate required fields
                    if not all([s3_bucket, s3_folder, file_name]):
                        logger.error(f"Missing required fields in document: {document}")
                        continue
                    
                    # Construct source and destination S3 keys
                    source_key = f"{s3_folder}/{file_name}" if s3_folder else file_name
                    destination_key = f"Destination/{file_name}"
                    
                    logger.info(f"Copying file from s3://{s3_bucket}/{source_key} to s3://{s3_bucket}/{destination_key}")
                    
                    # Copy the file from source to destination
                    copy_source = {
                        'Bucket': s3_bucket,
                        'Key': source_key
                    }
                    
                    s3_client.copy_object(
                        CopySource=copy_source,
                        Bucket=s3_bucket,
                        Key=destination_key
                    )
                    
                    logger.info(f"Successfully copied file {file_name} to Destination folder")
                    total_processed_documents += 1
                    
                except ClientError as e:
                    logger.error(f"S3 operation failed for file {document.get('file_name', 'unknown')}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing document {document.get('file_name', 'unknown')}: {e}")
                    continue
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message body as JSON: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing record: {e}")
            continue
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'File processing completed',
            'processedRecords': len(event.get('Records', [])),
            'processedDocuments': total_processed_documents
        })
    }