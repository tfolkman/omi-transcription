import json
import logging
import os
from datetime import datetime

import boto3
import certifi
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class R2Storage:
    def __init__(self, config):
        self.account_id = config.R2_ACCOUNT_ID
        self.access_key = config.R2_ACCESS_KEY_ID
        self.secret_key = config.R2_SECRET_ACCESS_KEY
        self.bucket_name = config.R2_BUCKET_NAME
        self.environment = config.ENVIRONMENT

        # Set SSL certificate bundle for CI environments
        os.environ["SSL_CERT_FILE"] = certifi.where()
        os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

        # Configure boto3 with better SSL handling for CI environments
        boto_config = Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "adaptive"},
            s3={"addressing_style": "path"},
        )

        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="auto",
            config=boto_config,
            verify=certifi.where(),  # Use certifi's CA bundle
        )

        logger.info(f"R2 Storage initialized for {self.environment} environment using bucket: {self.bucket_name}")

    def save_transcript(self, transcript_data: dict) -> str | None:
        """
        Save transcript to R2
        Returns the key if successful, None otherwise
        """
        try:
            # Generate key based on timestamp
            now = datetime.utcnow()
            uid = transcript_data.get("uid", "unknown")
            timestamp = transcript_data.get("timestamp", int(now.timestamp()))

            # Key structure: transcripts/year/month/uid_timestamp.json
            key = f"transcripts/{now.year}/{now.month:02d}/{uid}_{timestamp}.json"

            # Add metadata to the transcript
            transcript_data["saved_at"] = now.isoformat()
            transcript_data["environment"] = self.environment
            transcript_data["r2_key"] = key

            # Upload to R2
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(transcript_data, indent=2),
                ContentType="application/json",
            )

            logger.info(f"Saved transcript to R2: {key}")
            return key

        except ClientError as e:
            logger.error(f"Error saving transcript to R2: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error saving to R2: {e}")
            return None

    def get_transcript(self, key: str) -> dict | None:
        """
        Retrieve a single transcript by key
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            data: dict = json.loads(response["Body"].read())
            return data

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"Transcript not found: {key}")
            else:
                logger.error(f"Error retrieving transcript: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving from R2: {e}")
            return None

    def list_user_transcripts(self, uid: str, limit: int = 10) -> list[dict]:
        """
        List transcripts for a specific user
        Returns list of transcript metadata (not full content)
        """
        transcripts = []

        try:
            # We need to list all transcripts and filter by UID
            # since R2 doesn't support advanced filtering
            paginator = self.client.get_paginator("list_objects_v2")

            page_iterator = paginator.paginate(Bucket=self.bucket_name, Prefix="transcripts/")

            for page in page_iterator:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    key = obj["Key"]
                    # Check if this transcript belongs to the user
                    if f"/{uid}_" in key:
                        transcripts.append(
                            {"key": key, "size": obj["Size"], "last_modified": obj["LastModified"].isoformat()}
                        )

                        if len(transcripts) >= limit:
                            break

                if len(transcripts) >= limit:
                    break

            # Sort by last modified date (newest first)
            transcripts.sort(key=lambda x: x["last_modified"], reverse=True)

            # Fetch full transcript data for the requested limit
            full_transcripts = []
            for transcript_meta in transcripts[:limit]:
                transcript = self.get_transcript(transcript_meta["key"])
                if transcript:
                    full_transcripts.append(transcript)

            return full_transcripts

        except ClientError as e:
            logger.error(f"Error listing transcripts: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing transcripts: {e}")
            return []

    def get_stats(self, month: int | None = None, year: int | None = None) -> dict:
        """
        Get statistics for transcripts
        If month/year not specified, uses current month
        """
        now = datetime.utcnow()
        target_year = year or now.year
        target_month = month or now.month

        prefix = f"transcripts/{target_year}/{target_month:02d}/"

        try:
            # List all objects for the month
            response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)

            total_files = 0
            total_size = 0
            total_cost = 0.0

            if "Contents" in response:
                for obj in response["Contents"]:
                    total_files += 1
                    total_size += obj["Size"]

                    # Fetch the transcript to get cost data
                    transcript = self.get_transcript(obj["Key"])
                    if transcript and "cost_usd" in transcript:
                        total_cost += transcript["cost_usd"]

            return {
                "month": f"{target_year}-{target_month:02d}",
                "total_files": total_files,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "total_cost_usd": round(total_cost, 4),
                "storage_cost_usd": round(total_size / (1024 * 1024 * 1024) * 0.015, 4),  # R2 pricing
            }

        except ClientError as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "month": f"{target_year}-{target_month:02d}",
                "total_files": 0,
                "total_size_mb": 0,
                "total_cost_usd": 0,
                "storage_cost_usd": 0,
            }

    def delete_transcript(self, key: str) -> bool:
        """
        Delete a transcript from R2
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted transcript: {key}")
            return True

        except ClientError as e:
            logger.error(f"Error deleting transcript: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Test R2 connection and bucket access
        """
        try:
            # Try to list objects (with limit 1 to minimize data transfer)
            self.client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)
            logger.info(f"Successfully connected to R2 bucket: {self.bucket_name}")
            return True

        except ClientError as e:
            logger.error(f"Failed to connect to R2: {e}")
            return False
