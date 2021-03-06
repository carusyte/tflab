#!/bin/sh

python test13.py --prefetch=2 --profile --trace --vol_size=512 --skip_init_test --ds=file --dir=gs://carusytes_bucket/wcc_trn
if [ $? -eq 0 ]; then
    sleep 15
    echo "Training complete, shutting down vm." | mail -s "Training Complete" 3110798@qq.com
    echo 'syncing file system...'
    sync
    echo 'shutting down vm...'
    sudo shutdown -h now
else
    echo FAIL
fi