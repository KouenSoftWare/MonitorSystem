#!/usr/bin/env python
# encoding: utf-8

import os

Rules = "universal"  # universal,master,node


def memory():
    p = os.popen("free -m -s 1 -c 2")
    data = p.read().strip().split('\n')
    p.close()
    mem = list(filter(lambda x: x and x.isdigit(), data[1].split(' ')))
    return {"total": mem[0], "used": mem[1], "free": mem[2], "shared": mem[3], "cache": mem[4], "availavle": mem[5]}


def check(data, cache):
    if eval(data['used'])/eval(data['total']) > 95:
        return False, "Memory lack: %s" % str(eval(data['used'])/eval(data['total']))
    return True, "Memory Recover"
