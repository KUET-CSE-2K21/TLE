#!/bin/bash

# Get to a predictable directory, the directory of this script
cd "$(dirname "$0")"

[ -e environment ] && . ./environment

while true; do
    pip install seaborn lxml pycairo PyGObject aiocache firebase-admin recordtype requests pytz beautifulsoup4 topggpy disnake Flask
    FONTCONFIG_FILE=$PWD/extra/fonts.conf python -m tle

    (( $? != 42 )) && break

    echo '==================================================================='
    echo '=                       Restarting                                ='
    echo '==================================================================='
done
