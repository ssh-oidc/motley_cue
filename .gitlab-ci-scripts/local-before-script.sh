#!/bin/bash

echo "### local-before-script.sh #####################################"
echo -n "find python3 version: "
python3 --version
ls -l `which python3`
ls -l /etc/alternatives/python3*
ls -l /usr/bin/python3*

export DEBIAN_FRONTEND=noninteractive
echo "END local-before-script.sh #####################################"
