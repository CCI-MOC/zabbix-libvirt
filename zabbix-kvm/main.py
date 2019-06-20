"""The main module that orchestrates everything"""

import json
import time
import functools
import configparser


from pyzabbix import ZabbixMetric, ZabbixSender
from pyzabbix_socketwrapper import PyZabbixPSKSocketWrapper
from libvirt_zabbix import ZabbixLibvirt

DOMAIN_KEY = "libvirt.domain.discover"
VNICS_KEY = "libvirt.nic.discover"
VDISKS_KEY = "libvirt.disk.discover"
CONFIG_FILE = "/etc/zabbix-kvm/config.ini"
HOSTS_FILE = "/etc/zabbix-kvm/iplist.txt"


def get_hosts():
    """Read the ips/dns names from a file and return those bad boys"""

    with open(HOSTS_FILE) as hostfile:
        data = hostfile.read()
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
