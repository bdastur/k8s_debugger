#!/usr/bin/env python
# -*- coding: utf-8 -*-


import boto3
import json


def writeToS3(bucketName, key, data, region="us-east-1", profile="default"):
    """
    Write the object to the S3 bucket

    Args:
        bucketName (str): Name of the S3 bucket
        key (str): Path within the bucket where the object will be stored
        data (dict/str): The data to write (JSON object or string)
        profile (str, optional): AWS profile name to use. Defaults to None (uses default profile).
        region (str, optional): AWS region. Defaults to 'us-east-1'.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # Create a boto3 session with the specified profile and region
        session = boto3.Session(profile_name=profile, region_name=region)

        # Create an S3 client
        client = session.client('s3')

        # Convert data to string if it's a dictionary/JSON object
        if isinstance(data, dict):
            data_str = json.dumps(data)
        else:
            data_str = str(data)

        # Upload the data to S3
        client.put_object(
            Bucket=bucketName,
            Key=key,
            Body=data_str
        )

        print(f"Successfully wrote object to s3://{bucketName}/{key}")
        return True

    except Exception as e:
        print(f"Error writing to S3: {str(e)}")
        return False


def readFromS3(bucketName, key, region="us-east-1", profile="default", as_json=True):
    """
    Read a JSON/string object from an S3 bucket at the specified path.

    Args:
        bucket_name (str): Name of the S3 bucket
        path (str): Path within the bucket where the object is stored
        profile_name (str, optional): AWS profile name to use. Defaults to None (uses default profile).
        region (str, optional): AWS region. Defaults to 'us-east-1'.
        as_json (bool, optional): Whether to parse the content as JSON. Defaults to True.

    Returns:
        dict/str: The object read from S3 (as dict if as_json=True, otherwise as string)
        None: If there was an error
    """
    try:
        # Create a boto3 session with the specified profile and region
        session = boto3.Session(profile_name=profile, region_name=region)

        # Create an S3 client
        s3_client = session.client('s3')

        # Get the object from S3
        response = s3_client.get_object(
            Bucket=bucketName,
            Key=key
        )

        # Read the content
        content = response['Body'].read().decode('utf-8')

        # Parse as JSON if requested
        if as_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                print("Warning: Content could not be parsed as JSON, returning as string")
                return content
        else:
            return content

    except Exception as e:
        print(f"Error reading from S3: {str(e)}")
        return None



