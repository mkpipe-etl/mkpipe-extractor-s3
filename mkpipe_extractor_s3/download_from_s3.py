import os
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError


def upload_folder_to_s3(
    folder_path, bucket_name, s3_prefix='', table_name='', aws_access_key=None, aws_secret_key=None
):
    """
    Upload a folder and its contents to an S3 bucket.

    :param folder_path: Path to the folder to upload
    :param bucket_name: S3 bucket name
    :param s3_prefix: S3 prefix (folder path in S3 bucket) to upload files under
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

        # Walk through the directory
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                # Construct S3 object key (path)
                s3_key = os.path.join(
                    s3_prefix, table_name, os.path.relpath(file_path, folder_path)
                ).replace('\\', '/')

                # Upload the file
                s3_client.upload_file(file_path, bucket_name, s3_key)
                print(f'Uploaded {file_path} to s3://{bucket_name}/{s3_key}')

        
        message = f"All files in '{folder_path}' have been uploaded to bucket '{bucket_name}' under prefix '{s3_prefix}'."
        

    except FileNotFoundError:
        print(f'The folder {folder_path} was not found.')
        raise
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

