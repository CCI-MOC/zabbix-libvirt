"""The main module that orchestrates everything"""

import json
import functools
from pyzabbix import ZabbixMetric, ZabbixSender
from pyzabbix_socketwrapper import PyZabbixPSKSocketWrapper
from libvirt_zabbix import ZabbixLibvirt
from errors import LibvirtConnectionError, DomainNotFoundError
from helper import config, load_config, get_hosts, setup_logging

DOMAIN_KEY = "libvirt.domain.discover"
VNICS_KEY = "libvirt.nic.discover"
VDISKS_KEY = "libvirt.disk.discover"


def main():
    """main I guess"""
    # Setup logging
    logger = setup_logging(__name__, LOG_FILE)
    host_list = get_hosts(HOSTS_FILE)

    custom_wrapper = functools.partial(
        PyZabbixPSKSocketWrapper, identity=PSK_IDENTITY, psk=bytes(bytearray.fromhex(PSK)))

    zabbix_sender = ZabbixSender(
        zabbix_server=ZABBIX_SERVER, socket_wrapper=custom_wrapper)

    all_discovered_domains = []
    all_discovered_vnics = []
    all_discovered_vdisks = []
    combined_metrics = []

    for host in host_list:

        logger.info("Starting to process host: %s", host)
        uri = "qemu+ssh://root@" + host + "/system?keyfile=" + KEY_FILE

        try:
            zbxlibvirt = ZabbixLibvirt(uri)
        except LibvirtConnectionError as err:
            logger.warning(err)
            continue
        except Exception as err:
            logger.exception(err)
            raise

        try:
            all_discovered_domains += zbxlibvirt.discover_domains()
            all_discovered_vnics += zbxlibvirt.discover_all_vnics()
            all_discovered_vdisks += zbxlibvirt.discover_all_vdisks()
            combined_metrics.extend(zbxlibvirt.all_metrics())
        except DomainNotFoundError as err:
            # FIXME: Catching domain not found error here and then continuing the loop
            # here causes us to skip over all other domains on that host.
            # We should catch this in the other module where we are processing each domain.
            logger.warning(err)
            continue
        except Exception as err:
            logger.exception(err)
            raise

    logger.info("Sending packet")
    zabbix_sender.send([ZabbixMetric(HOST_IN_ZABBIX, DOMAIN_KEY,
                                     json.dumps({"data": all_discovered_domains}))])
    zabbix_sender.send([ZabbixMetric(HOST_IN_ZABBIX, VNICS_KEY,
                                     json.dumps({"data": all_discovered_vnics}))])
    zabbix_sender.send([ZabbixMetric(HOST_IN_ZABBIX, VDISKS_KEY,
                                     json.dumps({"data": all_discovered_vdisks}))])
    zabbix_sender.send(combined_metrics)


if __name__ == "__main__":
    load_config()
    LOG_FILE = config['general']['LOG_DIR'] + "zabbix-libvirt.log"
    PSK = config['general']['PSK']
    PSK_IDENTITY = config['general']['PSK_IDENTITY']
    HOST_IN_ZABBIX = config['general']['HOST_IN_ZABBIX']
    ZABBIX_SERVER = config['general']['ZABBIX_SERVER']
    HOSTS_FILE = config['general']['HOSTS_FILE']
    KEY_FILE = config['general']['KEY_FILE']
    main()
