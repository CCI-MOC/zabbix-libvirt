# zabbix-libvirt

This repository contains a set of scripts to monitor Virtual Machines on hosts using the libvirt API. It is still a work in progress.

We developed this to monitor our openstack cluster.

Features summary:

1. Discover running domains/instances on the virtualization hosts.
2. Discover all network interfaces and attached drives.
3. Gather CPU Usage, Memory Usage, Network I/O stats, and drives attached.
4. Create a host in zabbix corresponding to each VM/instance; and use PSK to send data to it.
5. Metrics about deleted instances are kept for 90 days before deletion.

## Installation requirements

* packages on the OS
`yum install -y openssl-devel libvirt-devel gcc python-devel`

* python packages
`pip install configparser sslpsk py-zabbix libvirt-python`

* zabbix 4.2

## Deploy

1. Create a configuration file (see `examples/config.ini`) at `/etc/zabbix-libvirt/`.
2. Create a hosts file (see `examples/hosts.txt`) and put the path to it in the config file.
3. The script needs to connect as the root user, but it only needs to access libvirtd; so create an ssh key-pair with limited permissions.
4. Call `main.py` with whatever frequency your zabbix server can handle. You can setup a cron job for that.

