#!/bin/sh
if [ $# -ne 1 ]
then
    echo 'usage: ./record target'
    exit 
fi
target_name=$1
arr=(${target_name//'/'/ })
log_name=${arr[-1]}"_log"

echo "Writing logged output to "$log_name
./bin/tee $log_name | LD_PRELOAD=./bin/mmap_dump.so $1 

chmod +rw ./maps.*