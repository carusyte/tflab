from time import strftime
from datetime import datetime
from google.cloud import storage as gcs
from loky import get_reusable_executor
from retrying import retry
import sys
import os
import re
import multiprocessing
import numpy as np
import gzip
import json
import tempfile as tmpf
import input_file2

gcs_client = None
_executor = None


def _getExecutor(workers=multiprocessing.cpu_count()):
    global _executor
    if _executor is not None:
        return _executor
    _executor = get_reusable_executor(
        max_workers=workers,
        # initializer=_init,
        # initargs=(db_pool_size, db_host, db_port, db_pwd),
        timeout=1800)
    return _executor


def print_n_retry(exception):
    print(exception)
    return True


@retry(retry_on_exception=print_n_retry,
       stop_max_attempt_number=7,
       wait_exponential_multiplier=1000,
       wait_exponential_max=32000)
def _upload_gcs(file, bucket_name, object_name):
    global gcs_client
    if gcs_client is None:
        gcs_client = gcs.Client()
    bucket = gcs_client.get_bucket(bucket_name)
    blob = bucket.blob(object_name)
    # with open(file, 'rb') as f:
    blob.upload_from_file(file, rewind=True, content_type='application/json')


# @retry(retry_on_exception=print_n_retry,
#        stop_max_attempt_number=7,
#        wait_exponential_multiplier=1000,
#        wait_exponential_max=32000)
def _delete_blobs(bucket_name, blob_names):
    """Deletes blobs from the bucket."""
    global gcs_client
    if gcs_client is None:
        gcs_client = gcs.Client()
    bucket = gcs_client.get_bucket(bucket_name)
    for bn in blob_names:
        try:
            # print('{} deleting {}'.format(strftime("%H:%M:%S"), bn))
            blob = bucket.blob(bn)
            blob.delete()
        except:
            print('failed to delete {}: \n{}'.format(bn, sys.exc_info()[0]))


def _write_file(fileobj, payload):
    with gzip.GzipFile(fileobj=fileobj, mode='wb') as fout:
        fout.write(json.dumps(
            payload, separators=(',', ':')).encode('utf-8'))
        fout.flush()


def _write_result(path, indices, records, del_used, rpaths):
    result = {'records': records}
    s = re.search('gs://([^/]*)/(.*)', path)
    bucket = s.group(1)
    # generate result file in memory
    # tmp = tmpf.SpooledTemporaryFile(max_size=1024*1024*100)
    with tmpf.TemporaryFile(mode='wb+') as tmp:
        _write_file(tmp, result)
        # upload to gcs (overwrite)
        objn = '{}/r_{}.json.gz'.format(s.group(2),
                                        datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3])
        _upload_gcs(tmp, bucket, objn)
    print('{} result file uploaded to {}'.format(strftime("%H:%M:%S"), objn))
    # update tasklist item status
    sep = input_file2.TALIST_SEP
    with open(input_file2.TASKLIST_FILE, 'rb+') as f:
        for idx in indices:
            f.seek(idx)
            ln = f.readline()
            # locate position of status code
            idx = idx + ln.find(sep)+len(sep)
            f.seek(idx)
            f.write('O')
        f.flush()
    # delete used inference file if needed
    if del_used:
        _delete_blobs(bucket, rpaths)

    return os.getpid()


def write_result(path, indices, records, del_used, rpaths):
    return _getExecutor().submit(_write_result, path, indices, records, del_used, rpaths)
    # return _write_result(path, indices, records)


def shutdown():
    if _executor:
        _executor.shutdown()
