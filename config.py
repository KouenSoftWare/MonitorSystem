#!/usr/bin/env python
# encoding: utf-8

ZookeeperServers = "127.0.0.1:2181"
ZookeeperPath = "/locks/monitor"

CDH = ["rjbdmaster1:7180", "rjbdmaster2:7180"]
CdhUser = 'admin'
CdhPassword = 'admin'

Mysql = ["rjbdmaster1:3180", "rjbdmaster2:3180"]
MysqlUser = "root"
MysqlPassword = "rjbigdata"

YarnDomain = ["rjbdnode2:8088", "rjbdnode1:8088"]
SparkAppListURL = ["http://%s/cluster/scheduler" % i for i in YarnDomain]
SparkRunningURL = ["http://%s/cluster/apps/RUNNING" % i for i in YarnDomain]
SparkFailedURL = ["http://%s/cluster/apps/FAILED" % i for i in YarnDomain]
SparkKilledURL = ["http://%s/cluster/apps/KILLED" % i for i in YarnDomain]

ProjectName = "RuijieNetwork"

ServerPort = "31818"

WxUser = 'wxe3591a8b7edc740d'
WxPassword = 'vu1MqmUSxHY9TjLKr6p6vOh9oxaEM8RHFZLBJRZWB-9znSwQQ6h2kI8ax6TJ79N8'
WxAppID = 1000006
