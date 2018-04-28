#!/usr/bin/env python
# encoding: utf-8

import os
import socket

Rules = "universal"  # universal,master,node


def monitor():
    ip = socket.gethostbyname(socket.gethostname())
    p = os.popen("ifconfig")
    ifconfig = p.read().split(": flags=")
    p.close()

    idx = 0
    for row in range(0, len(ifconfig)):
        if ip in ifconfig[row]:
            idx = row-1
            break

    net = filter(lambda x: x, ifconfig[idx].split('\n'))[-1]

    p = os.popen("ethtool %s | grep Speed" % net)
    speedMsg = p.read().strip().split(" ")[-1]
    p.close()

    speed = -1
    for i in range(len(speedMsg), -1, -1):
        if speedMsg[0:i].isdigit():
            speed = int(speedMsg[0:i])
            break

    return {
        'speed': speed,
        'unit': speedMsg.replace(str(speed), '')
    }


def check(data, cache):
    if "Mb" not in data['unit']:
        return False, "Speed unit != Mb/s:%s" % data['unit']
    if data['speed'] < 1000:
        return False, "Speed Slow:%d" % data['speed']

    return True, "Speed Recover(%d%s)" % (data['speed'], data['unit'])
