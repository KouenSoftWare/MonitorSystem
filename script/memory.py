#!/usr/bin/env python
# encoding: utf-8

import os


def memory():
    p = os.popen("free -m -s 1 -c 2")
    data = p.read().strip().split('\n')
    p.close()
    mem = list(filter(lambda x: x and x.isdigit(), data[1].split(' ')))
    return {"total": mem[0], "used": mem[1], "free": mem[2], "shared": mem[3], "cache": mem[4], "availavle": mem[5]}


def check(data):
    if eval(data['used'])/eval(data['total']) > 80:
        return "Memory lack: %s" % str(eval(data['used'])/eval(data['total']))
    return ""
