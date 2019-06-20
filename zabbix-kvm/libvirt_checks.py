#! /usr/bin/python

"""
This file holds the class that creates a connection to libvirt and provides
various methods to get useful information
"""

import libvirt
import sys
import time
from xml.etree import ElementTree


SLEEP_TIME = 1


class LibvirtConnection(object):
    """This class opens a connection to libvirt and provides with methods
    to get useuful information about domains.
    """

    @staticmethod
    def libvirt_callback(userdata, err):
        pass

    def __init__(self, uri=None):
        """Creates a read only connection to libvirt"""
        self.conn = libvirt.openReadOnly(uri)
        if self.conn == None:
            sys.stdout.write("Failed to open connection to the hypervisor")
            # FIXME: Need to figure out if exiting is the right thing to do here.
            sys.exit(1)

        # We set this because when libvirt errors are raised, they are still
        # printed to console (stderr) even if you catch them.
        # This is a problem with libvirt API.
        # See https://stackoverflow.com/questions/45541725/avoiding-console-prints-by-libvirt-qemu-python-apis
        libvirt.registerErrorHandler(f=self.libvirt_callback, ctx=None)

    def _get_domain_by_uuid(self, domain_uuid_string):
        """Find the domain by uuid and return domain object"""
        domain = self.conn.lookupByUUIDString(domain_uuid_string)
        if domain == None:
            sys.stdout.write("Failed to find domain: " + domain_uuid_string)
            sys.exit(1)
        return domain

    def discover_domains(self):
        """Return all active domains.

        Inactive domains will be discovered in the next run if they become active"""
        domains = self.conn.listAllDomains()
        domains = [{"{#DOMAINNAME}": domain.name(), "{#DOMAINUUID}": domain.UUIDString()}
                   for domain in domains if domain.isActive()]
        return domains

    def discover_all_vnics(self):
        """Discover all vnics for all domains.

        Returns a list of dictionary with vnics name and associated domain's uuid"""
        domains = self.conn.listAllDomains()
        domains = [domain for domain in domains if domain.isActive()]

        vnics = []
        for domain in domains:
            tree = ElementTree.fromstring(domain.XMLDesc())
            elements = tree.findall('devices/interface/target')
            vnics.extend([{"{#VNIC}": element.get('dev'),"{#DOMAINUUID}": domain.UUIDString()} for element in elements])

        return vnics

    def discover_all_vdisks(self):
        """Discover all virtual disk drives.

        Returns a list of dictionary with vdisks name and associated domain's uuid"""
        domains = self.conn.listAllDomains()
        domains = [domain for domain in domains if domain.isActive()]

        vdisks = []
        for domain in domains:
            tree = ElementTree.fromstring(domain.XMLDesc())
            elements = tree.findall('devices/disk/target')
            vdisks = [{"{#VDISK}": element.get('dev'), "{#DOMAINUUID}": domain.UUIDString()} for element in elements]

        return vdisks

    def get_memory(self, domain_uuid_string):
        """Get memorystats for domain.

        Here's a mapping of what the output from
        virsh / libvirt means to what is displayed by linux's `free` command.

        available = total
        unused = free
        usable = available
        actual = Current memory allocated to the VM(it's not the same as total in `free` command).

        The API returns the output in KiB, so we multiply by 1024 to return bytes for zabbix.
        """
        domain = self._get_domain_by_uuid(domain_uuid_string)

        try:
            stats = domain.memoryStats()
        except libvirt.libvirtError:
            # If the domain is not running, then the memory usage is 0.
            # If the error is due to other reasons, then re-raise the error.
            if domain.isActive():
                raise
            else:
                return {"free": 0, "available": 0, "current_allocation": 0}

        return {"free": stats.get("unused", 0) * 1024,
                "available": stats.get("usable", 0) * 1024,
                "current_allocation": stats.get("actual", 0) * 1024}

    def get_virt_host(self):
        """Get virtualizatio host's hostname"""
        return self.conn.getHostname()

    def get_cpu(self, domain_uuid_string):
        """Get CPU statistics. Libvirt returns the stats in nanoseconds.

        Returns the overall percent usage.
        """
        domain = self._get_domain_by_uuid(domain_uuid_string)

        try:
            stats_1 = domain.getCPUStats(True)[0]
            time.sleep(SLEEP_TIME)
            stats_2 = domain.getCPUStats(True)[0]
        except libvirt.libvirtError:
            # If the domain is not running, then the cpu usage is 0.
            # If the error is due to other reasons, then re-raise the error.
            if domain.isActive():
                raise
            else:
                return {"cpu_time": 0, "system_time": 0, "user_time": 0}

        number_of_cpus = domain.info()[3]

        def _percent_usage(time1, time2):
            return (time2-time1) / (number_of_cpus * SLEEP_TIME * 10**7)

        return {"cpu_time": _percent_usage(stats_1['cpu_time'], stats_2['cpu_time']),
                "system_time": _percent_usage(stats_1['system_time'], stats_2['system_time']),
                "user_time": _percent_usage(stats_1['user_time'], stats_2['user_time'])}

    def get_ifaceio(self, domain_uuid_string, iface):
        """Get Network I / O"""
        domain = self._get_domain_by_uuid(domain_uuid_string)

        try:
            stats = domain.interfaceStats(iface)
        except libvirt.libvirtError:
            if domain.isActive():
                raise
            else:
                return {"read": 0, "write": 0}

        return {"read": str(stats[0]), "write": str(stats[4])}

    def get_diskio(self, domain_uuid_string, disk):
        """Get Disk I / O"""
        domain = self._get_domain_by_uuid(domain_uuid_string)

        try:
            stats = domain.blockStatsFlags(disk)
        except libvirt.libvirtError:
            if domain.isActive():
                raise
            else:
                return {'wr_total_times': 0, 'rd_operations': 0,
                        'flush_total_times': 0, 'rd_total_times': 0,
                        'rd_bytes': 0, 'flush_operations': 0,
                        'wr_operations': 0, 'wr_bytes': 0}

        return stats

    def is_active(self, domain_uuid_string):
        """Returns 1 if domain is active, 0 otherwise."""
        domain = self._get_domain_by_uuid(domain_uuid_string)
        sys.stdout.write(str(domain.isActive()))


if __name__ == "__main__":
    """Do main things"""
    print("Main called")
