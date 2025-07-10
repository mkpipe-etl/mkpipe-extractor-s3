import os
import gc
import datetime
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark import SparkConf
import pyspark.sql.functions as F

from mkpipe.config import load_config
from mkpipe.utils import log_container, Logger
from mkpipe.functions_db import get_db_connector
from mkpipe.functions_spark import remove_partitioned_parquet, get_parser
from mkpipe.utils.base_class import PipeSettings
from mkpipe.plugins.registry_jar import collect_jars
from .download_from_s3 import download_folder_from_s3


class S3Extractor:
    def __init__(self, config, settings):
        if isinstance(settings, dict):
            self.settings = PipeSettings(**settings)
        else:
            self.settings = settings
        self.connection_params = config['connection_params']
        self.bucket_name = self.connection_params['bucket_name']
        self.s3_prefix = self.connection_params['s3_prefix']
        self.aws_access_key = self.connection_params['aws_access_key']
        self.aws_secret_key = self.connection_params['aws_secret_key']

        self.table = config['table']
        self.pass_on_error = config.get('pass_on_error', None)
        self.file_type = config.get('file_type', 'parquet')

        config = load_config()
        connection_params = config['settings']['backend']
        db_type = connection_params['variant']
        self.backend = get_db_connector(db_type)(connection_params)

    def create_spark_session(self):
        jars = collect_jars()
        conf = SparkConf()
        conf.setAppName(__file__)
        conf.setMaster('local[*]')
        conf.set('spark.driver.memory', self.settings.spark_driver_memory)
        conf.set('spark.executor.memory', self.settings.spark_executor_memory)
        conf.set('spark.jars', jars)
        conf.set('spark.driver.extraClassPath', jars)
        conf.set('spark.executor.extraClassPath', jars)
        conf.set('spark.network.timeout', '600s')
        conf.set('spark.sql.parquet.datetimeRebaseModeInRead', 'CORRECTED')
        conf.set('spark.sql.parquet.datetimeRebaseModeInWrite', 'CORRECTED')
        conf.set('spark.sql.parquet.int96RebaseModeInRead', 'CORRECTED')
        conf.set('spark.sql.parquet.int96RebaseModeInWrite', 'CORRECTED')
        conf.set('spark.sql.session.timeZone', self.settings.timezone)
        conf.set(
            'spark.driver.extraJavaOptions', f'-Duser.timezone={self.settings.timezone}'
        )
        conf.set(
            'spark.executor.extraJavaOptions',
            f'-Duser.timezone={self.settings.timezone}',
        )
        conf.set(
            'spark.driver.extraJavaOptions',
            '-XX:ErrorFile=/tmp/java_error%p.log -XX:HeapDumpPath=/tmp',
        )

        return SparkSession.builder.config(conf=conf).getOrCreate()

    def extract_full(self, t):
        logger = Logger(__file__)
        spark = self.create_spark_session()
        try:
            name = t['name']
            target_name = t['target_name']
            message = dict(table_name=target_name, status='extracting')
            logger.info(message)

            write_mode = 'overwrite'
            s3_local_path = os.path.abspath(
                os.path.join(self.settings.ROOT_DIR, 'artifacts', 's3', target_name)
            )

            parquet_path = os.path.abspath(
                os.path.join(self.settings.ROOT_DIR, 'artifacts', target_name)
            )

            s3_table_path = os.path.join(self.s3_prefix, name)
            download_folder_from_s3(
                bucket_name=self.bucket_name,
                s3_prefix=s3_table_path,
                local_dir=s3_local_path,
                aws_access_key=self.aws_access_key,
                aws_secret_key=self.aws_secret_key,
            )

            data = {'path': s3_local_path}
            df = get_parser(self.file_type)(data, self.settings)
            df.write.parquet(parquet_path, mode=write_mode)
            
            count_col = len(df.columns)
            count_row = df.count()

            data = {
                'table_name': target_name,
                'path': parquet_path,
                'file_type': 'parquet',
                'number_of_columns': count_col,
                'number_of_rows': count_row,
                'write_mode': write_mode,
                'pass_on_error': self.pass_on_error,
                'replication_method': 'full',
            }
            message = dict(
                table_name=target_name,
                status='extracted',
                meta_data=data,
            )
            logger.info(message)
            df.unpersist()
            gc.collect()
            return data
        finally:
            # Ensure Spark session is closed
            spark.stop()
            remove_partitioned_parquet(s3_local_path)

    @log_container(__file__)
    def extract(self):
        extract_start_time = datetime.datetime.now()
        logger = Logger(__file__)
        logger.info({'message': 'Extracting data from S3...'})
        t = self.table
        try:
            target_name = t['target_name']
            replication_method = t.get('replication_method', None)
            if self.backend.get_table_status(target_name) in ['extracting', 'loading']:
                logger.info(
                    {'message': f'Skipping {target_name}, already in progress...'}
                )
                data = {
                    'table_name': target_name,
                    'status': 'completed',
                    'replication_method': 'full',
                }
                return data

            self.backend.manifest_table_update(
                name=target_name,
                value=None,  # Last point remains unchanged
                value_type=None,  # Type remains unchanged
                status='extracting',  # ('completed', 'failed', 'extracting', 'loading')
                replication_method=replication_method,  # ('incremental', 'full')
                error_message='',
            )
            return self.extract_full(t)

        except Exception as e:
            message = dict(
                table_name=target_name,
                status='failed',
                type='pipeline',
                error_message=str(e),
                etl_start_time=str(extract_start_time),
            )
            self.backend.manifest_table_update(
                target_name,
                None,
                None,
                status='failed',
                replication_method=replication_method,
                error_message=str(e),
            )
            if self.pass_on_error:
                logger.warning(message)
                return None
            else:
                raise Exception(message) from e
