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
import re
import sys
import json
import time
import Queue
import socket
import config
import logging
import requests
import datetime
import threading
from kazoo.client import KazooClient
from requests.auth import HTTPBasicAuth
from logging.handlers import TimedRotatingFileHandler


sys.path.append(os.getcwd()+"/script")


class ZooKeeper(object):
    def __init__(self, logger=None):
        self.zk_client = None
        self.logger = logger
        self.lock_handle = None

        self.create_client()

    def create_client(self):
        try:
            self.zk_client = KazooClient(
                hosts=config.ZookeeperServers, 
                logger=self.logger
            )

            self.zk_client.start()
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
        return json.loads(data[0])

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

    def create_socket(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.server_ip, int(self.server_port)))
            return sock
        except (Exception, ), ex:
            self.logger("connect error: %s" % str(ex))
            self.stop()
            return None

    def stop(self):
        self.alive = False

    def run(self):
        while self.alive:
            sock = self.create_socket()

            if not sock:
                break

            msg = json.dumps(collectData())
            msgSize = str(len(msg))
            package = "^%15s%s" % (msgSize, msg)

            try:
                sock.sendall(package)
            except (Exception, ):
                self.logger("Send Data Error")

            sock.close()
            time.sleep(config.CollectInterval)


def collectData():
    monitorDatas = {
        "host": socket.gethostname(),
        "ip": socket.gethostbyname(socket.gethostname()),
        'list': []
    }

    for m in filter(lambda x: "monitor" in gRemoteModules.get(x, {})):
        try:
            monitorDatas['list'].append({"name": m, "data": gRemoteModules[m]['monitor']()})
        except (Exception,):
            pass
    return monitorDatas


class ServerWork(threading.Thread):
    def __init__(self, logger, queue):
        super(ServerWork, self).__init__()
        self.alive = True
        self.logger = logger
        self.queue = queue

    def stop(self):
        self.alive = False

    def run(self):
        cache = {}
        while self.alive:
            datas = list()
            while 1:
                try:
                    data = self.queue.get_nowait()
                    datas.append(data)
                except Queue.Empty:
                    break
            if datas:
                msg = []
                for func in [cdhServerStatus, sparkTaskStatus, mysqlSyncStatus]:
                    msg.append(func(cache))

                for i in datas:
                    for j in i['list']:
                        if "check" in gRemoteModules.get(j['name'], {}):
                            try:
                                cache.setdefault(j['name'], {'status': True, 'cache': {}})
                                checkRet, checkMsg = gRemoteModules[j['name']]['check'](
                                    data=j['data'], cache=cache[j['name']]['cache'])

                                if not checkRet:
                                    cache[j['name']]['status'] = False
                                    msg.append("%s %s" % (i['ip'], checkMsg))
                                else:
                                    if not cache[j['name']]['status']:
                                        cache[j['name']]['status'] = True
                                        msg.append("%s %s" % (i['ip'], checkMsg))

                            except (Exception, ):
                                self.logger("Check %s.%s Error!" % (i['ip'], j['name']))

                if msg:
                    sendMsgToWx(msg="\n".join(map(lambda x: "%s %s" % (config.ProjectName, x),
                                              filter(lambda x: x != "", msg))))

            time.sleep(config.NoticeInterval)


def cdhServerStatus(cache):
    cdh_status = set()
    cache.setdefault('cdh_status', set())
    cache.setdefault('cdh_notice', dict())

    host = "http://%s/api/v11/clusters/cluster1/services" % config.CDH[0]
    try:
        requests.get(host)
    except (Exception, ):
        host = "http://%s/api/v11/clusters/cluster1/services" % config.CDH[1]

    headers = {"Accept": "application/json",
               "Content-Type": "application/json"}

    ret = requests.request(
        "GET", host, headers=headers,
        auth=HTTPBasicAuth(config.CdhUser, config.CdhPassword))
    ret.raise_for_status()

    normal = set()
    for i in ret.json()['items']:
        if i['healthSummary'] != 'GOOD':
            if i['name'] not in cache['cdh_status']:
                cdh_status.add(i['name'])
                cache['cdh_status'].add(i['name'])
        else:
            if i['name'] in cache['cdh_status']:
                cache['cdh_status'].remove(i['name'])
                normal.add(i['name'])

    for service in cdh_status:
        cache['cdh_notice'].setdefault(service, config.NoticeMaxCount)
        if cache['cdh_notice'][service]:
            cache['cdh_notice'][service] -= 1
        else:
            cdh_status.remove(service)

    for service in normal:
        cache['cdh_notice'][service] = config.NoticeMaxCount

    if cdh_status:
        return u"CDH异常组件 %s" % ",".join(cdh_status)

    if normal:
        return u"CDH恢复正常组件 %s" % ",".join(normal)

    return ""


def sparkTaskStatus(cache):
    result = set()

    init = False
    if 'spark' not in cache:
        cache.setdefault('spark', {'killed': set(), 'failed': set()})
        init = True

    for prefix, urls in [('killed', config.SparkKilledURL),
                         ('failed', config.SparkFailedURL)]:
        for url in urls:
            for row in re.findall(
                    'cluster/app/(app.*?)\'>.*</a>","(.*?)","(.*?)","(.*?)","(.*?)","(.*?)","(.*?)","(.*?)","(.*?)","(.*?)","(.*?)","(.*?)"',
                    requests.get(url).text
            ):
                if not init:
                    if row[0] not in cache['spark'][prefix]:
                        result.add("%s(%s)" % (row[2], prefix))
                cache['spark'][prefix].add(row[0])

    # 通过Schedule和config对比streaming丢失情况

    if result:
        return "Spark %s" % ','.join(list(result))
    else:
        return ""


def mysqlSyncStatus(cache):
    cmd = "mysql -u{User} -p{Password} -h{Host} -P{Port} -e 'show slave status \\G'"
    cache.setdefault('mysql', config.NoticeMaxCount)

    for h in config.Mysql:
        ip, port = h.split(':')
        p = os.popen(cmd.format(
            User=config.MysqlUser,
            Password=config.MysqlPassword,
            Host=ip, Port=port
        ))
        ret = p.read()
        p.close()

        if "Slave_IO_Running: Yes" not in ret and "Slave_SQL_Running: Yes" not in ret and cache['mysql']:
            cache['mysql'] -= 1
            return u"Mysql 同步异常:%s" % ip
    if cache['mysql'] != config.NoticeMaxCount:
        cache['mysql'] = config.NoticeMaxCount
        return u"Mysql 同步回复正常"
    return ""


class Server(threading.Thread):
    def __init__(self, logger):
        super(Server, self).__init__()
        self.alive = True
        self.logger = logger
        self.queue = Queue.Queue(100)
        self.socket = socket.socket()
        self.socket.bind(('0.0.0.0', int(config.ServerPort)))
        self.socket.listen(10)

        self.work = ServerWork(logger=logger, queue=self.queue)
        self.work.start()

        self.cli = Client(ip='0.0.0.0', port=config.ServerPort, logger=logger)
        self.cli.start()

    def stop(self):
        self.alive = False
        self.work.stop()
        self.cli.stop()

    def run(self):
        def handle_request(conn, address):
            try:
                data = conn.recv(16)
                if not data:
                    conn.close()

                pos = data.find('^')
                if pos != 0:
                    conn.close()
                    return

                msgSize = int(data[1:].strip())
                self.logger.info('recv msg size: %d' % msgSize)
                msgBody = conn.recv(msgSize)

                if not msgBody:
                    self.logger.info('recv msg body error: %s' % address[0])
                    conn.close()
                    return

                data = json.loads(msgBody)
                self.queue.put(data, block=True)

            except (Exception, ):
                pass

        while self.alive:
            cli, addr = self.socket.accept()
            t = threading.Thread(target=handle_request, args=(cli, addr))
            t.start()
        self.socket.close()


class Gitee(threading.Thread):
    def run(self):
        while 1:
            global gRemoteModules
            os.system("rm -rf %s/.git" % os.getcwd()+"/script")
            os.system("git clone {GiteePath} {LocalPath} --depth=1".format(
                GiteePath=config.GiteePath, LocalPath=os.getcwd()+"/script"))

            ruler = ["master" if "master" in socket.gethostname() else "node"][0]
            for name in map(lambda x: x.replace('.py', ''),
                            filter(lambda x: ".py" in x and ".pyc" not in x,
                                   os.listdir(os.getcwd() + "/script"))):
                scriptModule = __import__(name)
                if "Ruler" not in scriptModule.__dict__ or scriptModule.Ruler in ['universal', ruler]:
                    gRemoteModules[name] = __import__(name).__dict__

            time.sleep(config.GiteeCheckInterval)


def sendMsgToWx(msg):
    def get_token():
        token_url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken'
        values = {
            'corpid': config.WxUser,
            'corpsecret': config.WxPassword
        }
        req = requests.post(token_url, params=values)
        data = json.loads(req.text)
        return data["access_token"]
    try:
        wx_url = "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=" + get_token()
        requests.post(wx_url, data=json.dumps({
            "touser": "@all",
            "toparty": "@all",
            "msgtype": "text",
            "agentid": config.WxAppID,
            "text": {
                "content": "%s %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:$S"), msg)
            },
            "safe": 0
        }, ensure_ascii=False).encode("UTF-8"))
    except (Exception, ):
        pass


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
    git = Gitee()
    git.start()
    while 1:
        if not git.isAlive():
            git = Gitee()
            git.start()

        zkCli = ZooKeeper(logger=logger)
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
    gRemoteModules = {}
    main()
