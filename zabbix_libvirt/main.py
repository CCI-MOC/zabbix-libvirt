"""The main module that orchestrates everything"""

import json
import functools
import time

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
    vnics = libvirt_connection.discover_vnics(domain_uuid_string)
    vdisks = libvirt_connection.discover_vdisks(domain_uuid_string)

    zabbix_sender.send([ZabbixMetric(domain_uuid_string, VNICS_KEY,
                                     json.dumps(vnics))])
    zabbix_sender.send([ZabbixMetric(domain_uuid_string, VDISKS_KEY,
                                     json.dumps(vdisks))])

    metrics = []

    def _create_metric(stats, item_type, item_subtype=None):
        """Helper function to create and append to the metrics list"""
        for stat, value in stats.iteritems():

            if item_subtype is not None:
                stat = "{},{}".format(item_subtype, stat)

            key = "libvirt.{}[{}]".format(item_type, stat)
            metrics.append(ZabbixMetric(domain_uuid_string, key, value))

    for vdisk in vdisks:
        stats = libvirt_connection.get_diskio(
            domain_uuid_string, vdisk["{#VDISK}"])
        _create_metric(stats, "disk", vdisk["{#VDISK}"])

    # 3. Gather metrics for all nics
    for vnic in vnics:
        stats = libvirt_connection.get_ifaceio(
            domain_uuid_string, vnic["{#VNIC}"])
        _create_metric(stats, "nic", vnic["{#VNIC}"])

    _create_metric(libvirt_connection.get_memory(domain_uuid_string), "memory")
    _create_metric(libvirt_connection.get_cpu(domain_uuid_string), "cpu")
    _create_metric(libvirt_connection.get_misc_attributes(
        domain_uuid_string), "instance")
    zabbix_sender.send(metrics)


def cleanup_hosts(hosts, zabbix_api):
    """
    This function takes care of hosts that are in zabbix but no longer exist
    in openstack.
    If the host was not updated in a configurable amount of time, then we delete it.
    """

    # This can be any arbritary item that we know exists and is generally updated.
    item_key = "libvirt.instance[name]"
    retention_period = 90 * 24 * 60 * 60
    hosts_to_be_deleted = []

    for host in hosts:

        host_id = zabbix_api.get_host_id(host)
        assert host_id is not None, "Host ID is none for: " + host

        lastclock = zabbix_api.get_item(host_id, item_key, "lastclock")

        if lastclock is None:
            logger.warning("Host '%s' has no lastclock", host)
            continue

        if int(time.time()) - int(lastclock) > retention_period:
            logger.info("Staging host  '%s' to be deleted", host)
            hosts_to_be_deleted.append(host_id)

    if hosts_to_be_deleted != []:
        zabbix_api.delete_hosts(hosts_to_be_deleted)


def main():
    """main I guess"""
    host_list = get_hosts(HOSTS_FILE)

    custom_wrapper = functools.partial(
        PyZabbixPSKSocketWrapper, identity=PSK_IDENTITY, psk=bytes(bytearray.fromhex(PSK)))
    zabbix_sender = ZabbixSender(
        zabbix_server=ZABBIX_SERVER, socket_wrapper=custom_wrapper, timeout=30)

    all_openstack_instances = []

    with ZabbixConnection(USER, "https://" + ZABBIX_SERVER, PASSWORD) as zapi:

        groupid = zapi.get_group_id(GROUP_NAME)
        templateid = zapi.get_template_id(TEMPLATE_NAME)

        for host in host_list:
            logger.info("Starting to process host: %s", host)
            uri = "qemu+ssh://root@" + host + "/system?keyfile=" + KEY_FILE

            try:
                libvirt_connection = LibvirtConnection(uri)
            except LibvirtConnectionError as error:
                # Log the failure to connect to a host, but continue processing
                # other hosts.
                logger.exception(error)
                continue

            domains = libvirt_connection.discover_domains()
            all_openstack_instances.extend(domains)
            for domain in domains:
                try:
                    if zapi.get_host_id(domain) is None:
                        zapi.create_host(
                            domain, groupid, templateid, PSK_IDENTITY, PSK)
                    update_instance(domain, libvirt_connection, zabbix_sender)
                except DomainNotFoundError as error:
                    # This may happen if a domain is deleted after we discover
                    # it. In that case we log the error and move on.
                    logger.exception(error)
                except ZabbixAPIException as error:
                    logger.exception(error)
                    raise

        all_zabbix_hosts = zapi.get_all_hosts()
        hosts_not_in_openstack = list(
            set(all_zabbix_hosts) - set(all_openstack_instances))

        cleanup_hosts(hosts_not_in_openstack, zapi)


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
    logger = setup_logging(__name__, LOG_FILE)
    main()
