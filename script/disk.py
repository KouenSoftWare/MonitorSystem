#!/usr/bin/env python
# encoding: utf-8

import os


Rules = "universal"  # universal,master,node


def monitor():
    p = os.popen("df -h | grep dev/sd")
    diskInfo = p.read().strip().split("\n")
    p.close()

    returnData = {}
    for row in diskInfo:
        db, total, use, residue, per, d = list(filter(lambda x: x, row.split(' ')))
        returnData[d] = {"db": db, "total": total, "use": use, "residue": residue, "percent": per}

    p = os.popen("cat /etc/fstab | grep UUID")
    fstab = p.read().strip().split("\n")
    p.close()
    for row in fstab:
        uuid, d, system, _, _, _ = list(filter(lambda x: x, row.split(' ')))
        returnData.setdefault(d, {})
        returnData[d]["uuid"] = uuid
    return returnData


def check(data, cache):
    checkDirs = {"/data/data1", "/data/data2", "/data/data3",
                 "/data/data4", "/data/data5", "/data/data6"}

    lackDirs = checkDirs - set(data.keys())

    lackFstabDirs = set()
    lackDfDirs = set()

    for d in data:
        if "total" not in data[d]:
            lackDfDirs.add(d)
        elif "uuid" not in data[d]:
            lackFstabDirs.add(d)

    msg = []
    for dirs, errMsg in [(lackDirs, u"无配置无挂载"),
                         (lackFstabDirs, u"无配置"),
                         (lackDfDirs, u"无挂载")]:
        for d in dirs:
            msg.append(u"%s(%s)" % (d, errMsg))

    if msg:
        return False, u"DiskErr %s" % u",".join(msg)
    return True, "Disk Recover."
