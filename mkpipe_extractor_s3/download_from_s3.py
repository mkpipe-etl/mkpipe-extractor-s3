import os
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError


def download_folder_from_s3(
    bucket_name, s3_prefix, local_dir, aws_access_key=None, aws_secret_key=None
):
    """
    Download a folder and its contents from an S3 bucket to a local directory.

    :param bucket_name: S3 bucket name
    :param s3_prefix: S3 prefix (folder path in S3 bucket) to download files from
    :param local_dir: Local directory to download the files to
    :param aws_access_key: AWS access key (optional, uses default credentials if not provided)
    :param aws_secret_key: AWS secret key (optional, uses default credentials if not provided)
    """
    try:
        # Create an S3 client
        if aws_access_key and aws_secret_key:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
            )
        else:
            s3_client = boto3.client('s3')  # Use default credentials

        # List objects in the specified S3 prefix (folder)
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix)

        # Ensure the local directory exists
        os.makedirs(local_dir, exist_ok=True)

        # Download each file
        for page in pages:
            if 'Contents' not in page:
                print(f"No files found in the S3 prefix '{s3_prefix}'.")
                return

            for obj in page['Contents']:
                # Get the S3 object key (file path in S3)
                s3_key = obj['Key']
                # Construct the local file path
                relative_path = os.path.relpath(s3_key, s3_prefix)
                local_file_path = os.path.join(local_dir, relative_path)

                # Ensure the local directory structure exists
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

                # Download the file
                s3_client.download_file(bucket_name, s3_key, local_file_path)
                print(f'Downloaded s3://{bucket_name}/{s3_key} to {local_file_path}')

        message = f"All files in S3 prefix '{s3_prefix}' have been downloaded to '{local_dir}'."

    except NoCredentialsError:
        print('Credentials not available.')
        raise
    except PartialCredentialsError:
        print('Incomplete credentials provided.')
        raise
    except Exception as e:
        print(f'An error occurred: {e}')
        raise

    return message
