#!/bin/sh

# compile preeny
git submodule update --init --recursive
sudo apt-get install -y libini-config-dev
cd preeny
./cmake-build.sh
cd ../
mv -f ./preeny/build/lib ./test/preeny


# 编译
mkdir ./bin/
gcc ./source/loader/core_dump.c -o ./bin/core_dump.so -fPIC -shared -ldl
gcc ./source/loader/mmap_dump.c -o ./bin/mmap_dump.so -fPIC -shared -ldl
gcc ./source/loader/tee.c  -o ./bin/tee
gcc ./test/replay_test/replay_test.c -o ./bin/replay_test
gcc ./test/replay_test/get_bp.c -o ./bin/get_bp_test
# 暂时需要angr和pwnlib
python3 -m pip show angr 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install angr
fi
python3 -m pip show pwn 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install pwn
fi

python3 -m pip show pygdbmi 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install pygdbmi
fi

python3 -m pip show cstruct 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install cstruct
fi

python3 -m pip show termcolor 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install termcolor 
fi

python3 -m pip show jinja2 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install jinja2
fi

apt-get install -y graphviz
python3 -m pip show graphviz 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install graphviz
fi

python3 -m pip show seaborn 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install seaborn
fi

python3 -m pip show numpy 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install numpy
fi

python3 -m pip show structlog 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install structlog
fi

python3 -m pip show python-json-logger 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install python-json-logger
fi

