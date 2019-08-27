# Documentations?

## New instances

1. The script connects to the virtualization hosts (read from a file) and discover all domains on each host.
2. For every domain/instance/VM that is discovered a corresponding host is created on a zabbix server (if the host does not already exist). In case the host was created in an earlier run and disabled for cleanup, it will be re-enabled.
3. A new host is always added to a standard host group (configurable) and to another host group named after the instance's openstack project UUID. This way you can easily find metrics for all instances belonging to an openstack project.
4. The host group named after project UUID is automatically created before the host is added.
4. A template (configurable) is applied to the host which has the right items created. (It will be uploaded to this repository).
5. Disks and nics are discovered on the host, and their metrics are reported.


## Cleanup tasks

At the end of each run, the script will find out what instances no longer exist (HOSTS_IN_ZABBIX - HOSTS_IN_OPENSTACK).

From this list, the script will

1. Disable the hosts in zabbix if the host was never discovered again after 1 hour. We want to wait an hour before we disable hosts in case a compute was unreachable for sometime. Thougm the host will be re-enabled automatically if it discovered even after the 1 hour period.
2. Hosts that have not been discoverd for more than 90 days (will be made configurable) will be deleted.

## Notes about items

### CPU time

This is the absolute time in nanoseconds reported by libvirt. This is quite useless on its own, but is requried for calculating percent cpu usage. Since is the sum of cpu time for all CPUs, we divide it by the number of CPUs before sending it to zabbix.

### CPU Usage % cpu_time

We calculate the cpu usage based on how [virt-manager](https://github.com/virt-manager/virt-manager/blob/728fd7cf7b6062563efd7419e0eb03527ad64dd5/virtManager/lib/statsmanager.py#L179) calculates it.

This item is dependent on the absolute cpu time. We use 2 levels of pre-processing for this item.

* First step is the built-in "Change per second". This calculates the difference between the current value and the previous value and divides it  by the delta of timestamps when those values were received. For accuracy, the time stamp is sent by the script right when the absolute cpu time is measured.


* The next step uses the javascript preprocessing function to cap the value between 0 and 100 percent. This preprocessing step is only available in zabbix 4.2.

We don't use calcuated items for this because, calculated always calculate even if no new data has been received.

So if the script is run every 5 minutes (meaning new data is sent every 5 minutes), then the percent cpu usage is averaged over the 5 minute period.

### Instance information

* Active: 1 indicates if an instance is running, 0 otherwise.
* Project UUID: The openstack project uuid that owns the instance. If the instance does not belong to openstack, then it will say "non-openstack-instance"
* User UUID: The openstack user uuid who created the instance.

### Memory

* Free and available memory is not reported for windows VMs.
