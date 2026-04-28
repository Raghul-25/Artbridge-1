import boto3
import os
from botocore.exceptions import ClientError

def test_dynamo_insert():
    print("Testing DynamoDB Connection and Insert...")
    
    # Connect to DynamoDB using boto3
    try:
        dynamodb = boto3.resource(
            'dynamodb',
            region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        )
        
        # Test connection
        print("Connected to AWS successfully.")
        
        table_name = "ArtBridgeProducts"
        table = dynamodb.Table(table_name)
        
        # Insert a sample product
        product_item = {
            'id': 'test-prod-001',
            'name': 'Test Dynamo Product',
            'price': '19.99',
            'category': 'Test',
            'description': 'A sample product inserted during DynamoDB connectivity testing.',
            'stock': 10
        }
        
        print(f"Attempting to insert product into table '{table_name}'...")
        response = table.put_item(Item=product_item)
        
        status_code = response.get('ResponseMetadata', {}).get('HTTPStatusCode')
        if status_code == 200:
            print("SUCCESS! Product inserted successfully.")
            print(f"Response: {response}")
        else:
            print(f"WARNING: Insert completed but got HTTP status code: {status_code}")
            
    except ClientError as e:
        print(f"AWS ClientError occurred: {e}")
        print("Make sure your AWS credentials are correct and the table exists.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_dynamo_insert()
