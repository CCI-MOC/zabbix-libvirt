"""Some tests"""

from libvirt_checks import LibvirtConnection
from zabbix_methods import ZabbixConnection
from helper import config, load_config

CONFIG_FILE = "/etc/zabbix-libvirt/config.ini"


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


def test_zabbix_connection_all():
    """Test the ZabbixConnection class

    The test will perform a bunch of CRUD operations and make assertions
    on the way that things are working as expected."""
    load_config()

    user = config['general']['API_USER']
    server = "https://" + config['general']['ZABBIX_SERVER']
    password = config['general']['PASSWORD']

    group_name = "openstack-instances"
    template_name = "moc_libvirt_single"
    correct_group_id = "15"
    correct_template_id = "10264"

    test_host_name = "apo12o12opk"

    with ZabbixConnection(user, server, password) as zapi:
        # check that we get the correct group ids
        groupid = zapi.get_group_id(group_name)
        templateid = zapi.get_template_id(template_name)
        assert groupid == correct_group_id
        assert templateid == correct_template_id

        # ensure that the test_host does/should not already exist.
        assert test_host_name not in zapi.get_all_hosts()
        assert zapi.get_host_id(test_host_name) is None

        # Create the host
        host_id = zapi.create_host(test_host_name, groupid, templateid)

        # Ensure that host is now created.
        assert test_host_name in zapi.get_all_hosts()
        assert zapi.get_host_id(test_host_name) == host_id

        deleted_hosts = zapi.delete_hosts([zapi.get_host_id(test_host_name)])
        assert deleted_hosts == [host_id]
        assert test_host_name not in zapi.get_all_hosts()
