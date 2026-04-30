"""
s3_uploader.py — Upload artisan product images to AWS S3.

Usage:
    from s3_uploader import upload_image

    url = upload_image(
        local_path  = "C:/Kiosk New/artbridge_photos/photo_001.jpg",
        artisan_id  = "42",
        product_id  = "abc123",
        slot        = 1          # 1, 2, 3 or 4
    )
    # returns "https://artbridge-images.s3.amazonaws.com/artisans/42/abc123/image_1.jpg"
    # returns None on failure
"""

import os
import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
S3_BUCKET  = os.environ.get("S3_BUCKET",  "artbridge-images")
REGION     = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Cache client across calls
_s3_client = None

def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=REGION)
    return _s3_client


def upload_image(local_path: str, artisan_id, product_id, slot: int) -> Optional[str]:
    """
    Upload a single image to S3 and return its public HTTPS URL.

    Parameters
    ----------
    local_path  : absolute path to the local JPEG/PNG file
    artisan_id  : artisan's ID (str or int)
    product_id  : unique product UUID or ID (str or int)
    slot        : photo slot number 1-4

    Returns
    -------
    str  : public URL  — e.g. https://artbridge-images.s3.amazonaws.com/...
    None : on any failure (caller should treat None as no image)
    """
    if not local_path or local_path == "placeholder":
        logger.debug(f"Skipping slot {slot} — no real path.")
        return None

    if not os.path.isfile(local_path):
        logger.warning(f"File not found for slot {slot}: {local_path}")
        return None

    ext        = os.path.splitext(local_path)[1].lower() or ".jpg"
    s3_key     = f"artisans/{artisan_id}/{product_id}/image_{slot}{ext}"
    content_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

    try:
        s3 = _get_s3()
        s3.upload_file(
            local_path,
            S3_BUCKET,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )
        url = f"https://{S3_BUCKET}.s3.{REGION}.amazonaws.com/{s3_key}"
        logger.info(f"Uploaded slot {slot} → {url}")
        return url

    except ClientError as e:
        logger.error(f"S3 upload failed for slot {slot}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error uploading slot {slot}: {e}")
        return None


def upload_product_images(local_paths: list, artisan_id, product_id) -> list:
    """
    Upload up to 4 images and return a list of 4 URLs (None where upload failed).

    Parameters
    ----------
    local_paths : list of up to 4 local file paths (None / 'placeholder' = skip)
    artisan_id  : artisan's ID
    product_id  : unique product ID / UUID

    Returns
    -------
    list of 4 items — each is a URL string or None
    """
    slots = (list(local_paths) + [None, None, None, None])[:4]
    urls  = []
    for i, path in enumerate(slots, start=1):
        url = upload_image(path, artisan_id, product_id, i)
        urls.append(url)
    return urls   # always length 4
