#!/bin/sh

../../bin/tee aaaa.txt | LD_PRELOAD=../../bin/mmap_dump.so ./easyheap && exit
