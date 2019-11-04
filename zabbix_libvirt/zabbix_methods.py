"""Create a host on zabbix server"""

import pyzabbix


class ZabbixConnection(object):
    """This class will provide an object that lets you create, update, delete,
    and get information about hosts.
    """

    def __init__(self, user, server, password):
        """Login so we have a session"""
        self.session = self.login(user, server, password)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.user.logout()

    @staticmethod
    def login(user, server, password):
        """Login to zabbix server"""
        return pyzabbix.ZabbixAPI(user=user, url=server, password=password)

    def create_host(self, host_name, groupids, templateid, tls_psk_identity, tls_psk):
        """Create a host in zabbix"""

        # The interfaces are arbritary here since we will only use zabbix trapper
        # items to communicate.
        interfaces = {"type": 1, "main": 1, "useip": 1, "ip": "127.0.0.1",
                      "dns": "", "port": "10069"}
        groups = [{"groupid": i} for i in groupids]
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

    def get_all_hosts(self, groupids=None):
        """
        Find all hosts.

        groupdis: Return only hosts that belong to the given groups. This means
        host belonging to either of the group ids in the list (a union).
        """
        if groupids is None:
            parameters = {"output": ["name"]}
        else:
            parameters = {"groupids": groupids, "output": ["name"]}
        results = self.session.do_request(
            "host.get", parameters)["result"]
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

    def get_host_status(self, host_name):
        """Return the montoring status for a host.
        It's weird, but status "0" represents that host is monitored(enabled),
        while "1" represents that host is not montitored (disabled)"""
        results = self.session.do_request(
            "host.get", {"filter": {"host": [host_name]},
                         "output": ["status", "name"]})["result"]
        if results == []:
            return None
        return results[0]["status"]

    def set_hosts_status(self, hostids, status):
        """Set monitoring statuses of mulitple hosts"""
        hosts = [{"hostid": hostid} for hostid in hostids]
        self.session.do_request(
            "host.massupdate", {"hosts": hosts, "status": status})

    def get_item(self, host_id, item_key, item_attribute="lastvalue"):
        """Get the value of an item with item_key on host with host_id.

        By default it will return the last value of the item"""

        results = self.session.do_request(
            "item.get", {"hostids": host_id, "search": {"key_": item_key}})["result"]
        for result in results:
            if result["key_"] == item_key:
                return result.get(item_attribute)
        return None

    def get_history(self, host_id, item_key, item_type=3, item_attribute="value"):
        """Return item history

        Sort fields by clock in descending order to get the latest items first.
        """
        itemids = self.get_item(host_id, item_key, item_attribute="itemid")
        results = self.session.do_request("history.get", {
            "history": item_type,
            "itemids": itemids,
            "limit": 1,
            "sortfield": "clock",
            "sortorder": "DESC"})["result"]
        if results == []:
            return None
        return results[0][item_attribute]

    def delete_hosts(self, host_ids):
        """Delete a host in zabbix"""
        result = self.session.do_request("host.delete", host_ids)["result"]
        return sorted(result["hostids"])

    def create_hostgroup(self, hostgroup):
        """Create a host group and return the group id"""
        result = self.session.do_request(
            "hostgroup.create", {"name": hostgroup})["result"]
        return result["groupids"][0]


def main():
    """Main things happen here"""
    print("I do nothing")


if __name__ == "__main__":
    main()
