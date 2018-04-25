#!/usr/bin/env python
# encoding: utf-8

import os


def monitor():
    p = os.popen("fdisk -l | grep Disk | grep /dev")
    data = p.read().strip().split('\n')
    p.close()

    ret = {}
    for i in data:
        arr = i.split(' ')
        ret[arr[1]] = arr[2]

    return ret


def check(data):
    return ""
