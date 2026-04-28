import os
import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
TABLE_PRODUCTS = os.environ.get("DYNAMO_TABLE_PRODUCTS", "ArtBridgeProducts")
TABLE_USERS    = os.environ.get("DYNAMO_TABLE_USERS", "ArtBridgeUsers")
TABLE_ORDERS   = os.environ.get("DYNAMO_TABLE_ORDERS", "ArtBridgeOrders")

_dynamo_resource = None

def get_dynamo_resource():
    global _dynamo_resource
    if _dynamo_resource is None:
        _dynamo_resource = boto3.resource('dynamodb', region_name=REGION)
    return _dynamo_resource

def insert_product(item: dict) -> bool:
    """Inserts a single product item into ArtBridgeProducts table."""
    try:
        table = get_dynamo_resource().Table(TABLE_PRODUCTS)
        table.put_item(Item=item)
        return True
    except ClientError as e:
        print(f"Error inserting product to DynamoDB: {e}")
        return False

def get_all_products() -> list:
    """Fetches all products from ArtBridgeProducts table."""
    try:
        table = get_dynamo_resource().Table(TABLE_PRODUCTS)
        response = table.scan()
        return response.get('Items', [])
    except ClientError as e:
        print(f"Error fetching products from DynamoDB: {e}")
        return []

def get_artisan_by_id(artisan_id: str) -> dict:
    """Fetches a single artisan from ArtBridgeUsers by ID."""
    if not artisan_id:
        return {}
    try:
        table = get_dynamo_resource().Table(TABLE_USERS)
        response = table.get_item(Key={'id': str(artisan_id)})
        return response.get('Item', {})
    except ClientError as e:
        print(f"Error fetching artisan {artisan_id} from DynamoDB: {e}")
        return {}

def get_products_with_artisans() -> list:
    """
    Fetches all products and attaches the corresponding artisan details.
    """
    products = get_all_products()
    result = []
    
    # Simple cache to avoid querying the same artisan multiple times
    artisan_cache = {}
    
    for p in products:
        # Convert float/Decimals to int/float if necessary, but returning as is mostly fine.
        product_item = dict(p)
        product_item["price"] = float(p.get("price", 0))
        
        artisan_id = p.get("artisan_id")
        artisan_data = None
        
        if artisan_id:
            if artisan_id not in artisan_cache:
                artisan_cache[artisan_id] = get_artisan_by_id(artisan_id)
            
            a = artisan_cache[artisan_id]
            if a:
                artisan_data = {
                    "name": a.get("name", "Unknown Artisan"),
                    "location": a.get("location", "Unknown Location"),
                    "rating": float(a.get("rating", 0.0))
                }
        
        if artisan_data is None:
            # Fallback if artisan not found or no ID provided
            artisan_data = {
                "name": "Unknown Artisan",
                "location": "Unknown Location",
                "rating": 0.0
            }
            
        product_item["artisan"] = artisan_data
        result.append(product_item)
        
    return result

def push_order_to_dynamo(order_item: dict) -> bool:
    """Inserts or updates a single order in ArtBridgeOrders table."""
    try:
        table = get_dynamo_resource().Table(TABLE_ORDERS)
        table.put_item(Item=order_item)
        return True
    except ClientError as e:
        print(f"Error pushing order to DynamoDB: {e}")
        return False

def fetch_all_orders_from_dynamo() -> list:
    """Fetches all orders from ArtBridgeOrders table."""
    try:
        table = get_dynamo_resource().Table(TABLE_ORDERS)
        response = table.scan()
        return response.get('Items', [])
    except ClientError as e:
        print(f"Error fetching orders from DynamoDB: {e}")
        return []
