#!/usr/bin/env python
# encoding: utf-8

"""
    1. auto load script/*.py, the py file has monitor function.
    2. auto load ./config.py, such zookeeper list, path
    3. two thread:
        the one is main that it's woring in heart and election master(zk temporary node)
        the second in work that it's woring the send data to server
"""
import os
import sys
import json
import time
import socket
import config
import gevent
import logging
import importlib
import threading
from gevent import socket, monkey
from kazoo.client import KazooClient
from logging.handlers import TimedRotatingFileHandler


monkey.patch_all()
sys.path.append(os.getcwd()+"/script")


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
        except (Exception, ), ex:
            logging.error("Create KazooClient failed! Exception: %s" % str(ex))

    def acquire(self):
        try:
            data = json.dumps({'ip': socket.gethostbyname(socket.gethostname()), 'port': str(config.ServerPort)})
            return self.zk_client.create(config.ZookeeperPath, data, ephemeral=True)
        except (Exception, ):
            return None

    def get(self):
        data = self.zk_client.get(config.ZookeeperPath)
        return json.loads(data)

    def stop(self):
        if self.zk_client:
            self.zk_client.stop()
            self.zk_client.close()
            self.zk_client = None

    def __del__(self):
        self.stop()


class Client(threading.Thread):
    def __init__(self, ip, port, logger):
        super(Client, self).__init__()
        self.alive = True
        self.logger = logger
        self.server_ip = ip
        self.server_port = port
        self.socket = None

        self.create_socket()

    def create_socket(self):
        if self.socket:
            self.socket.close()
            self.socket = None

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.server_ip, self.server_port))

    def stop(self):
        self.alive = False

    def run(self):
        while self.alive:
            functions = list(
                map(lambda x: __import__(x).monitor,
                    filter(lambda x: "monitor" in __import__(x).__dict__,
                           map(lambda x: x.replace('.py', ''),
                               filter(lambda x: ".py" in x and ".pyc" not in x,
                                      os.listdir(os.getcwd()+"/script")))))
            )

            monitorDatas = []
            for func in functions:
                try:
                    monitorDatas.append(func())
                except (Exception, ):
                    self.logger.info("script error in %s" % str(func.__code__))

            msg = json.dumps(monitorDatas)
            msgSize = str(len(msg))
            package = "^%15s%s" % (msgSize, msg)

            try:
                self.socket.sendall(package)
            except (Exception, ):
                self.logger.info("connect break, election again.")
                break

            time.sleep(60)
        self.socket.close()


class Server(threading.Thread):
    def __init__(self, logger):
        super(Server, self).__init__()
        self.alive = True
        self.logger = logger
        self.socket = socket.socket()
        self.socket.bind(('0.0.0.0', config.ServerPort))
        self.socket.listen(10)

    def stop(self):
        self.alive = False

    def run(self):
        def handle_request(conn):
            try:
                while True:
                    data = conn.recv(16)
                    if not data:
                        conn.close()

                    pos = data.find('^')
                    if pos == -1:
                        continue

                    if pos != 0:
                        data += conn.recv(pos)
                    msgSize = int(data[pos+1:].strip())
                    msgBody = conn.recv(msgSize)

                    if not msgBody:
                        conn.close()
                        break

                    data = json.loads(msgBody)
                    # collect data, sent msg to wx.
                    print data

            except OSError as e:
                print("client has been closed: %s" % str(e))
            except Exception as ex:
                print(ex)
            finally:
                conn.close()

        while self.alive:
            cli, addr = self.socket.accept()
            gevent.spawn(handle_request, cli)
        self.socket.close()


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
            logger.info("election: i'm server")
            p = Server(logger=logger)
            p.start()
            p.join()
        else:
            logger.info("election: i'm client")
            data = zkCli.get()
            p = Client(ip=data['ip'], port=data['port'], logger=logger)
            p.start()

            while not zkCli.acquire():
                time.sleep(5)

            p.stop()

        zkCli.stop()

if __name__ == '__main__':
    main()
