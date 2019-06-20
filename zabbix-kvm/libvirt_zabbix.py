#! /usr/bin/python

"""Perform libvirt checks and package the data for zabbix server."""


import sys
import json
import time
import functools
import configparser

import ssl
import sslpsk

from libvirt_checks import LibvirtConnection
from pyzabbix import ZabbixMetric, ZabbixSender


DOMAIN_KEY = "libvirt.domain.discover"
VNICS_KEY = "libvirt.nic.discover"
VDISKS_KEY = "libvirt.disk.discover"
CONFIG_FILE = "/etc/libvirt-checks/config.ini"
HOSTS_FILE = "/etc/libvirt-checks/iplist.txt"


def make_metric(item_id, item_type, parameter, value):
    """returns zabbix metric"""
    key = "libvirt.{}[{},{}]".format(item_type, item_id, parameter)
    return ZabbixMetric(HOST_IN_ZABBIX, key, value)


class ZabbixLibvirt(object):
    """This class uses LibvirtConnection to gather information and then uses
    ZabbixSender to send it to our zabbix server
    """

    def __init__(self, libvirt_uri=None):
        """main I guess"""
        self.conn = LibvirtConnection(libvirt_uri)

    def discover_domains(self):
        """
        Discover domains on the host and return the ZabbixMetric ready
        to be sent.
        """
        return self.conn.discover_domains()

    def discover_all_vnics(self):
        """Discover all nics and return the ZabbixMetric ready to be sent"""
        return self.conn.discover_all_vnics()

    def discover_all_vdisks(self):
        """Discover all nics and return the ZabbixMetric ready to be sent"""
        return self.conn.discover_all_vdisks()

    def _cpu_usage_metric(self):
        """Get CPU usage and create ZabbixMetric to send"""
        domains = self.conn.discover_domains()
        metrics = []

        for domain in domains:
            domain_uuid = domain["{#DOMAINUUID}"]
            stats = self.conn.get_cpu(domain_uuid)

            cpu_time = make_metric(
                domain_uuid, "cpu", "cpu_time", stats["cpu_time"])
            system_time = make_metric(
                domain_uuid, "cpu", "system_time", stats["system_time"])
            user_time = make_metric(
                domain_uuid, "cpu", "user_time", stats["user_time"])

            metrics.extend([cpu_time, system_time, user_time])

        return metrics

    def _instance_attributes(self):
        """Returns the metric with instance name and the name of the host"""
        domains = self.conn.discover_domains()
        metrics = []

        for domain in domains:
            domain_uuid = domain["{#DOMAINUUID}"]
            domain_name = domain["{#DOMAINNAME}"]

            domain_name = make_metric(
                domain_uuid, "instance", "name", domain_name)
            virt_host = make_metric(
                domain_uuid, "instance", "virt_host", self.conn.get_virt_host())
            metrics.extend([domain_name, virt_host])

        return metrics

    def _memory_usage_metric(self):
        """Get memory usage and create ZabbixMetric to send"""
        domains = self.conn.discover_domains()
        metrics = []

        for domain in domains:

            domain_uuid = domain["{#DOMAINUUID}"]
            stats = self.conn.get_memory(domain_uuid)

            free = make_metric(domain_uuid, "memory", "free", stats["free"])
            available = make_metric(
                domain_uuid, "memory", "available", stats["available"])
            current_allocation = make_metric(
                domain_uuid, "memory", "current_allocation", stats["current_allocation"])

            metrics.extend([free, available, current_allocation])

        return metrics

    def _ifaceio_metric(self):
        """Get interface usage metrics"""
        vnics = self.conn.discover_all_vnics()
        metrics = []

        for vnic in vnics:
            domain_uuid = vnic["{#DOMAINUUID}"]
            iface = vnic["{#VNIC}"]
            stats = self.conn.get_ifaceio(domain_uuid, iface)

            item_id = domain_uuid + "," + iface

            read = make_metric(item_id, "nic", "read", stats["read"])
            write = make_metric(item_id, "nic", "write", stats["write"])

            metrics.extend([read, write])
        return metrics

    def _diskio_metric(self):
        """Get interface usage metrics"""
        vdisks = self.conn.discover_all_vdisks()
        metrics = []

        for vdisk in vdisks:
            domain_uuid = vdisk["{#DOMAINUUID}"]
            vdrive = vdisk["{#VDISK}"]
            stats = self.conn.get_diskio(domain_uuid, vdrive)
            stat_types = stats.keys()

            item_id = domain_uuid + "," + vdrive

            for stat_type in stat_types:
                metric = make_metric(
                    item_id, "disk", stat_type, stats[stat_type])
                metrics.append(metric)

        return metrics

    def all_metrics(self):
        """Send all metrics"""
        metrics = []
        metrics = self._cpu_usage_metric()
        metrics.extend(self._memory_usage_metric())
        metrics.extend(self._ifaceio_metric())
        metrics.extend(self._diskio_metric())
        metrics.extend(self._instance_attributes())
        return metrics


class PyZabbixPSKSocketWrapper:
    """Implements ssl.wrap_socket with PSK instead of certificates.

    Proxies calls to a `socket` instance.

    Thanks to @KostyaEsmukov for writing this.
    See the comment and full example here:
    https://github.com/adubkov/py-zabbix/issues/114#issue-430052782
    """

    def __init__(self, sock, identity, psk):
        self.__sock = sock
        self.__identity = identity
        self.__psk = psk

    def connect(self, *args, **kwargs):
        # `sslpsk.wrap_socket` must be called *after* socket.connect,
        # while the `ssl.wrap_socket` must be called *before* socket.connect.
        self.__sock.connect(*args, **kwargs)

        # `sslv3 alert bad record mac` exception means incorrect PSK
        self.__sock = sslpsk.wrap_socket(
            self.__sock,
            # https://github.com/zabbix/zabbix/blob/f0a1ad397e5653238638cd1a65a25ff78c6809bb/src/libs/zbxcrypto/tls.c#L3231
            ssl_version=ssl.PROTOCOL_TLSv1_2,
            # https://github.com/zabbix/zabbix/blob/f0a1ad397e5653238638cd1a65a25ff78c6809bb/src/libs/zbxcrypto/tls.c#L3179
            ciphers="PSK-AES128-CBC-SHA",
            psk=(self.__psk, self.__identity),)

    def __getattr__(self, name):
        return getattr(self.__sock, name)


def get_hosts():
    """Read the ips/dns names from a file and return those bad boys"""

    with open(HOSTS_FILE) as file:
        data = file.read()
    host_list = [item.strip() for item in data.split() if "#" not in item]

    return host_list


def main():
    """main I guess"""
    custom_wrapper = functools.partial(
        PyZabbixPSKSocketWrapper, identity=PSK_IDENTITY, psk=bytes(bytearray.fromhex(PSK)))

    zabbix_sender = ZabbixSender(
        zabbix_server=ZABBIX_SERVER, socket_wrapper=custom_wrapper)

    host_list = get_hosts()

    all_discovered_domains = []
    all_discovered_vnics = []
    all_discovered_vdisks = []
    combined_metrics = []

    for host in host_list:
        print("***For host: " + str(host))
        uri = "qemu+ssh://root@" + host + "/system"
        zbxlibvirt = ZabbixLibvirt(uri)

        all_discovered_domains += zbxlibvirt.discover_domains()
        all_discovered_vnics += zbxlibvirt.discover_all_vnics()
        all_discovered_vdisks += zbxlibvirt.discover_all_vdisks()

        combined_metrics.extend(zbxlibvirt.all_metrics())

    print("***SENDING PACKET at ****" + str(time.ctime()))
    zabbix_sender.send([ZabbixMetric(HOST_IN_ZABBIX, DOMAIN_KEY,
                                     json.dumps({"data": all_discovered_domains}))])
    zabbix_sender.send([ZabbixMetric(HOST_IN_ZABBIX, VNICS_KEY,
                                     json.dumps({"data": all_discovered_vnics}))])
    zabbix_sender.send([ZabbixMetric(HOST_IN_ZABBIX, VDISKS_KEY,
                                     json.dumps({"data": all_discovered_vdisks}))])
    zabbix_sender.send(combined_metrics)


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    PSK = config['general']['PSK']
    PSK_IDENTITY = config['general']['PSK_IDENTITY']
    HOST_IN_ZABBIX = config['general']['HOST_IN_ZABBIX']
    ZABBIX_SERVER = config['general']['ZABBIX_SERVER']
    main()
