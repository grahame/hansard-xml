#!/bin/bash -x 

rm -rf venv
virtualenv --system-site-packages -p /usr/bin/python3.3 venv
./venv/bin/easy_install -U ipython requests
