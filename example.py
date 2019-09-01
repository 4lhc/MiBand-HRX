#!/usr/bin/env python
import sys
import time
import argparse
from datetime import datetime
from base import MiBand2
from constants import ALERT_TYPES
from threading import Thread, Event


parser = argparse.ArgumentParser()
parser.add_argument('-s', '--alert',  action='store_true',help='Send an alert to device')
parser.add_argument('-l', '--live',  action='store_true',help='Print live accel data')
parser.add_argument('-d', '--dump',  action='store_true',help='Dump accel data to file')
parser.add_argument('-i', '--init',  action='store_true',help='Initializes the device')
parser.add_argument('-m', '--mac', required=True, help='Mac address of the device')
args = parser.parse_args()

MAC = args.mac # sys.argv[1]

band = MiBand2(MAC, debug=True)
band.setSecurityLevel(level="medium")

if  args.init:
    if band.initialize():
        print("Init OK")
    band.disconnect()
    sys.exit(0)
else:
    band.authenticate()


if args.alert:
    print ('Message notif')
    band.send_alert(ALERT_TYPES.MESSAGE)

def f(g):
    print ('Raw accel :', g)

if args.live:
    band.start_raw_data_realtime( accel_raw_callback=f, duration=80)

def dump_to_file(g):
    fname="accel_dump.txt"
    length=1000
    with open(fname, 'w') as fp:
        while length > 0:
            length -= 1
            fp.writelines("{}\n".format(g))

if args.dump:
    band.start_raw_data_realtime(accel_raw_callback=dump_to_file)


band.disconnect()
