#!/bin/bash -x 

rm -rf venv
virtualenv --system-site-packages -p /usr/bin/python3.2 venv
./venv/bin/easy_install -U ipython requests
