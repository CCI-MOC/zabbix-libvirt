"""Create a host on zabbix server"""

import pyzabbix

CONFIG_FILE = "/etc/zabbix-libvirt/config.ini"


class ZabbixConnection(object):
    """This class will provide an object that lets you create, update, delete,
    and get information about hosts.
    """

    def __init__(self, user, server, password):
        """Initialize this bad boy"""
        self.session = self.login(user, server, password)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.user.logout()

    @staticmethod
    def login(user, server, password):
        """Login to zabbix server"""
        return pyzabbix.ZabbixAPI(user=user, url=server, password=password)

    def create_host(self, host_name, groupid, templateid, tls_psk_identity, tls_psk):
        """Create a host in zabbix"""

        # The interfaces are arbritary here since we will only use zabbix trapper
        # items to communicate.
        interfaces = {"type": 1, "main": 1, "useip": 1, "ip": "127.0.0.1",
                      "dns": "", "port": "10069"}
        groups = [{"groupid": groupid}]
        templates = [{"templateid": templateid}]

        results = self.session.do_request("host.create", {
            "host": host_name,
            "tls_connect": 2,
            "tls_accept": 2,
            "tls_psk_identity": tls_psk_identity,
            "tls_psk": tls_psk,
            "interfaces": interfaces,
            "groups": groups,
            "templates": templates})["result"]
        return results["hostids"][0]

    def get_all_hosts(self):
        """Find all monitored hosts"""
        results = self.session.do_request(
            "host.get", {"monitored_hosts": 1})["result"]
        return [result["name"] for result in results]

    def get_group_id(self, group_name):
        """Find the group id of a group"""
        results = self.session.do_request(
            "hostgroup.get", {"filter": {"name": [group_name]}})["result"]
        if results == []:
            return None
        return results[0]["groupid"]

    def get_template_id(self, template_name):
        """Return the template ID"""
        results = self.session.do_request(
            "template.get", {"filter": {"name": [template_name]}})["result"]
        if results == []:
            return None
        return results[0]["templateid"]

    def get_host_id(self, host_name):
        """Get host id"""
        results = self.session.do_request(
            "host.get", {"filter": {"host": [host_name]}})["result"]
        if results == []:
            return None
        return results[0]["hostid"]

    def get_item(self, host_id, item_key, item_attribute="lastvalue"):
        """Get the value of an item with item_key on host with host_id.

        By default it will return the last value of the item"""

        results = self.session.do_request(
            "item.get", {"hostids": host_id, "search": {"key_": item_key}})["result"]
        for result in results:
            if result["key_"] == item_key:
                return result.get(item_attribute)

    def delete_hosts(self, host_ids):
        """Delete a host in zabbix"""
        result = self.session.do_request("host.delete", host_ids)["result"]
        return sorted(result["hostids"])


def main():
    """Main things happen here"""
    print("I do nothing")


if __name__ == "__main__":
    main()
