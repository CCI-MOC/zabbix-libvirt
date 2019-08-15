"""The main module that orchestrates everything"""

import json
import functools

from pyzabbix import ZabbixMetric, ZabbixSender
from pyzabbix.api import ZabbixAPIException
from pyzabbix_socketwrapper import PyZabbixPSKSocketWrapper
from errors import LibvirtConnectionError, DomainNotFoundError
from helper import config, load_config, get_hosts, setup_logging
from zabbix_methods import ZabbixConnection
from libvirt_checks import LibvirtConnection

VNICS_KEY = "libvirt.nic.discover"
VDISKS_KEY = "libvirt.disk.discover"


def update_instance(domain_uuid_string, libvirt_connection, zabbix_sender):
    """Gather instance attributes for domain with `domain_uuid_string` using
    `libvirt_connection` and then send the zabbix metrics using `zabbix_sender`
    """
    # 1. Discover nics and disks, and send the discovery packet
    print("Updating instance")
    vnics = libvirt_connection.discover_vnics(domain_uuid_string)
    vdisks = libvirt_connection.discover_vdisks(domain_uuid_string)

    zabbix_sender.send([ZabbixMetric(domain_uuid_string, VNICS_KEY,
                                     json.dumps({"data": vnics}))])
    zabbix_sender.send([ZabbixMetric(domain_uuid_string, VDISKS_KEY,
                                     json.dumps({"data": vdisks}))])

    # FIXME: Perhaps a helper function can simplify the following stuff
    # 2. Gather metrics for all disks
    metrics = []
    for vdisk in vdisks:
        stats = libvirt_connection.get_diskio(
            domain_uuid_string, vdisk["{#VDISK}"])

        for stat, value in stats.iteritems():
            metrics.append(
                ZabbixMetric(domain_uuid_string, "libvirt.disk[{},{}]".format(vdisk["{#VDISK}"],
                                                                              stat), value))

    # 3. Gather metrics for all nics
    for vnic in vnics:
        stats = libvirt_connection.get_ifaceio(
            domain_uuid_string, vnic["{#VNIC}"])

        for stat, value in stats.iteritems():
            metrics.append(ZabbixMetric(
                domain_uuid_string, "libvirt.nic[{},{}]".format(vnic["{#VNIC}"], stat), value))

    # 4. Gather metrics for memory
    memory = libvirt_connection.get_memory(domain_uuid_string)
    for stat, value in memory.iteritems():
        metrics.append(ZabbixMetric(domain_uuid_string,
                                    "libvirt.memory[{}]".format(stat), value))

    # 5. Gather CPU metrics
    cpu = libvirt_connection.get_cpu(domain_uuid_string)
    for stat, value in cpu.iteritems():
        metrics.append(ZabbixMetric(domain_uuid_string,
                                    "libvirt.cpu[{}]".format(stat), value))
    # 6. Gather misc stats
    misc = libvirt_connection.get_misc_attributes(domain_uuid_string)
    for stat, value in misc.iteritems():
        metrics.append(ZabbixMetric(domain_uuid_string,
                                    "libvirt.instance[{}]".format(stat), value))

    zabbix_sender.send(metrics)
    print("Done updating")


def main():
    """main I guess"""

    logger = setup_logging(__name__, LOG_FILE)
    host_list = get_hosts(HOSTS_FILE)

    custom_wrapper = functools.partial(
        PyZabbixPSKSocketWrapper, identity=PSK_IDENTITY, psk=bytes(bytearray.fromhex(PSK)))
    zabbix_sender = ZabbixSender(
        zabbix_server=ZABBIX_SERVER, socket_wrapper=custom_wrapper, timeout=30)

    with ZabbixConnection(USER, "https://" + ZABBIX_SERVER, PASSWORD) as zapi:

        groupid = zapi.get_group_id(GROUP_NAME)
        templateid = zapi.get_template_id(TEMPLATE_NAME)

        for host in host_list:
            logger.info("Starting to process host: %s", host)
            uri = "qemu+ssh://root@" + host + "/system?keyfile=" + KEY_FILE

            try:
                libvirt_connection = LibvirtConnection(uri)
            except LibvirtConnectionError as error:
                print(error)
                logger.exception(error)
                continue
            except Exception as error:
                print(error)
                logger.exception(error)
                raise

            domains = libvirt_connection.discover_domains()
            for domain in domains:
                try:
                    if zapi.get_host_id(domain) is None:
                        zapi.create_host(
                            domain, groupid, templateid, PSK_IDENTITY, PSK)
                    update_instance(domain, libvirt_connection, zabbix_sender)
                except ZabbixAPIException as error:
                    print("************EXCEPTION************")
                    print(error)
                except DomainNotFoundError as error:
                    print(error)


if __name__ == "__main__":
    load_config()
    USER = config['general']['API_USER']
    PASSWORD = config['general']['PASSWORD']
    ZABBIX_SERVER = config['general']['ZABBIX_SERVER']
    LOG_FILE = config['general']['LOG_DIR'] + "zabbix-libvirt.log"
    PSK = config['general']['PSK']
    PSK_IDENTITY = config['general']['PSK_IDENTITY']
    HOSTS_FILE = config['general']['HOSTS_FILE']
    KEY_FILE = config['general']['KEY_FILE']
    GROUP_NAME = "openstack-instances"
    TEMPLATE_NAME = "moc_libvirt_single"
    main()
