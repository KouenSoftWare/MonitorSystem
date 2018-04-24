#!/usr/bin/env python
# encoding: utf-8

"""
    1. auto load script/*.py, the py file has monitor function.
    2. auto load ./config.py, such zookeeper list, path
    3. two thread:
        the one is main that it's woring in heart and election master(zk temporary node)
        the second in work that it's woring the send data to server
"""
import importlib
import time
import config
import logging
from logging.handlers import TimedRotatingFileHandler
import threading
from kazoo.client import KazooClient


class ZooKeeperLock(object):
    def __init__(self, logger=None, timeout=1):
        self.zk_client = None
        self.timeout = timeout
        self.logger = logger
        self.lock_handle = None

        self.create_client()

    def create_client(self):
        try:
            self.zk_client = KazooClient(
                hosts=config.ZookeeperServers, 
                logger=self.logger, timeout=self.timeout
            )

            self.zk_client.start(timeout=self.timeout)
        except Exception, ex:
            logging.error("Create KazooClient failed! Exception: %s" % str(ex))

    def acquire(self):
        try:
            return self.zk_client.create(config.ZookeeperPath, ephemeral=True)
        except Exception, ex:
            logging.error("create ephemeral node failed! Exception: %s" % str(ex))
            return None

    def stop(self):
        if self.zk_client:
            self.zk_client.stop()
            self.zk_client.close()
            self.zk_client = None

    def __del__(self):
        self.stop()


class Client(threading.Thread):
    def run(self):
        while 1:
            print u"我是客户端"
            time.sleep(10)


class Server(threading.Thread):
    def run(self):
        while 1:
            print u"我是服务器"
            time.sleep(10)


def settleLog():
    log_fmt = '%(asctime)s\tFile \"%(filename)s\",line %(lineno)s\t%(levelname)s: %(message)s'
    formatter = logging.Formatter(log_fmt)
    log_file_handler = TimedRotatingFileHandler(filename="logs/iDataMonitor", when="D", interval=1, backupCount=14)
    log_file_handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger()
    log.addHandler(log_file_handler)
    return log


def main():
    logger = settleLog()
    while 1:
        zkCli = ZooKeeperLock(logger=logger)
        if zkCli.acquire():
            # 设置服务器信息(ip, 端口)
            p = Server()
            p.start()
        else:
            # 读取服务器信息(ip, 端口)
            p = Client()
            p.start()

            while not zkCli.acquire():
                time.sleep(5)

        zkCli.stop()

if __name__ == '__main__':
    main()
