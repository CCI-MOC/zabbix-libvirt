#!/usr/bin/env python2
"""The main module that orchestrates everything"""

import json
import functools
import time
from multiprocessing import Pool

from pyzabbix import ZabbixMetric, ZabbixSender
from pyzabbix.api import ZabbixAPIException
from pyzabbix_socketwrapper import PyZabbixPSKSocketWrapper
from errors import LibvirtConnectionError, DomainNotFoundError
from helper import config, load_config, get_hosts, setup_logging
from zabbix_methods import ZabbixConnection
from libvirt_checks import LibvirtConnection

VNICS_KEY = "libvirt.nic.discover"
VDISKS_KEY = "libvirt.disk.discover"


def get_instance_metrics(domain_uuid_string, libvirt_connection):
    """Gather instance attributes for domain with `domain_uuid_string` using
    `libvirt_connection` and then send the zabbix metrics using `zabbix_sender`
    """
    # 1. Discover nics and disks, and send the discovery packet
    metrics = []
    vnics = libvirt_connection.discover_vnics(domain_uuid_string)
    vdisks = libvirt_connection.discover_vdisks(domain_uuid_string)

    metrics.append(ZabbixMetric(domain_uuid_string, VNICS_KEY,
                                json.dumps(vnics)))
    metrics.append(ZabbixMetric(domain_uuid_string, VDISKS_KEY,
                                json.dumps(vdisks)))

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
    return metrics


def process_host(host, zabbix_sender):
    """Takes in host, and then process the domains on that host"""
    print("Processing Host: %s", host)
    logger = setup_logging(__name__ + host, LOG_DIR + "/" + host)

    with ZabbixConnection(USER, "https://" + ZABBIX_SERVER, PASSWORD) as zabbix_api:

        openstack_group_id = zabbix_api.get_group_id(GROUP_NAME)
        templateid = zabbix_api.get_template_id(TEMPLATE_NAME)

        logger.info("Starting to process host: %s", host)
        uri = "qemu+ssh://root@" + host + "/system?keyfile=" + KEY_FILE

        try:
            libvirt_connection = LibvirtConnection(uri)
        except LibvirtConnectionError as error:
            # Log the failure to connect to a host, but continue processing
            # other hosts.
            print("Host %s errored out", host)
            logger.exception(error)
            return

        domains = libvirt_connection.discover_domains()
        for domain in domains:
            try:
                project = libvirt_connection.get_misc_attributes(domain)[
                    "project_uuid"]
                project_group_id = zabbix_api.get_group_id(project)

                if project_group_id is None:
                    project_group_id = zabbix_api.create_hostgroup(project)

                groupids = [openstack_group_id, project_group_id]

                if zabbix_api.get_host_id(domain) is None:
                    logger.info("Creating new instance: %s", domain)
                    zabbix_api.create_host(
                        domain, groupids, templateid, PSK_IDENTITY, PSK)

                metrics = get_instance_metrics(domain, libvirt_connection)
                zabbix_sender.send(metrics)
                logger.info("Domain %s is updated", domain)

            except DomainNotFoundError as error:
                # This may happen if a domain is deleted after we discover
                # it. In that case we log the error and move on.
                logger.error("Domain %s not found", domain)
                logger.exception(error)
            except ZabbixAPIException as error:
                logger.error("Zabbix API error")
                logger.exception(error)
                raise
    return domains


def cleanup_host(host):
    """
    This function takes care of hosts that are in zabbix but no longer exist
    in openstack.
    If the host was not updated in a configurable amount of time, then we delete it.
    """

    # This can be any arbritary item that we know exists and is generally updated.
    print("Cleanup Host: " + host)
    item_key = "libvirt.instance[name]"
    retention_period = 90 * 24 * 60 * 60

    with ZabbixConnection(USER, "https://" + ZABBIX_SERVER, PASSWORD) as zabbix_api:
        host_id = zabbix_api.get_host_id(host)
        assert host_id is not None, "Host ID is none for: " + host
        lastclock = zabbix_api.get_item(host_id, item_key, "lastclock")

    if lastclock is None:
        main_logger.warning("Host '%s' has no lastclock", host)
        return None

    if int(lastclock) == 0:
        main_logger.info("Last clock for host '%s is zero", host)
        return None

    if int(time.time()) - int(lastclock) > retention_period:
        main_logger.info("Staging host  '%s' to be deleted", host)
        return host_id

    return None


def main():
    """main I guess"""
    host_list = get_hosts(HOSTS_FILE)

    all_openstack_instances = []
    p = Pool(min(MAX_PROCESSES, len(host_list)))

    custom_wrapper = functools.partial(
        PyZabbixPSKSocketWrapper, identity=PSK_IDENTITY, psk=bytes(bytearray.fromhex(PSK)))
    zabbix_sender = ZabbixSender(
        zabbix_server=ZABBIX_SERVER, socket_wrapper=custom_wrapper, timeout=30)

    custom_process_host = functools.partial(
        process_host, zabbix_sender=zabbix_sender)

    results = filter(None, p.map(custom_process_host, host_list))

    for result in results:
        all_openstack_instances.extend(result)

    with ZabbixConnection(USER, "https://" + ZABBIX_SERVER, PASSWORD) as zapi:
        openstack_group_id = zapi.get_group_id(GROUP_NAME)
        all_zabbix_hosts = zapi.get_all_hosts([openstack_group_id])

        hosts_not_in_openstack = list(
            set(all_zabbix_hosts) - set(all_openstack_instances))

        hosts_to_be_deleted = []

        p = Pool(min(MAX_PROCESSES, len(hosts_not_in_openstack)))

        hosts_to_be_deleted = filter(None, p.map(
            cleanup_host, hosts_not_in_openstack))
        if hosts_to_be_deleted != []:
            zapi.delete_hosts(hosts_to_be_deleted)


if __name__ == "__main__":
    load_config()
    USER = config['general']['API_USER']
    PASSWORD = config['general']['PASSWORD']
    ZABBIX_SERVER = config['general']['ZABBIX_SERVER']
    LOG_DIR = config['general']['LOG_DIR']
    PSK = config['general']['PSK']
    PSK_IDENTITY = config['general']['PSK_IDENTITY']
    HOSTS_FILE = config['general']['HOSTS_FILE']
    KEY_FILE = config['general']['KEY_FILE']
    GROUP_NAME = "openstack-instances"
    TEMPLATE_NAME = "moc_libvirt_single"
    MAX_PROCESSES = 16
    main_logger = setup_logging(__name__, LOG_DIR + "/main.log")
    main()
