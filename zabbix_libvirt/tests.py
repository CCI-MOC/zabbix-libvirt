from libvirt_checks import LibvirtConnection
from errors import LibvirtConnectionError, DomainNotFoundError


def test_libvirt_all():
    """Test all methods in the LibvirtConnection class"""

    # The test will be updated in the future so I can actually assert
    # that all `get` methods actaully get the right thing. For now they
    # just check that everything runs without any errors

    conn = LibvirtConnection()

    domains = conn.discover_domains()

    for domain in domains:
        print domain
        print conn.get_virt_host()

        print conn.is_active(domain)
        print conn.get_cpu(domain)
        print conn.get_memory(domain)
        vdisks = conn.discover_vdisks(domain)
        vnics = conn.discover_vnics(domain)
        print vdisks
        print vnics

        for vdisk in vdisks:
            print conn.get_diskio(domain, vdisk["{#VDISK}"])

        for vnic in vnics:
            print conn.get_ifaceio(domain, vnic["{#VNIC}"])
