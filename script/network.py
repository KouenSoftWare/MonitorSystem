#!/usr/bin/env python
# encoding: utf-8

import os


def monitor():
    ret = {}
    # for h in ["rjbdmaster1", "rjbdmaster2", "rjbdnode1", "rjbdnode2", "rjbdnode3"]:
    for h in ["114.114.114.114", "www.baidu.com", "172.1.1.1"]:
        try:
            p = os.popen("ping %s -c 3" % h)
            ms = p.read().strip().split('\n')[-1].split(' ')[-2].split('/')
            p.close()
            ret[h] = {
                'min': ms[0],
                'avg': ms[1],
                'max': ms[2],
                'mdev': ms[3]
            }
        except (Exception, ):
            ret[h] = {}

    return ret


def check(data):
    badHost = []
    for host in data:
        if not data[host] or eval(data[host]['avg']) > 1000:
            badHost.append(host)
    if badHost:
        return "To %s Timeout/slowly" % ",".join(badHost)
    else:
        return ""
