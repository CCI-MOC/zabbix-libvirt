# zabbix-libvirt

This repository contains a set of scripts to monitor Virtual Machines on hosts using the libvirt API. It is still a work in progress.

Features:

1. Discover running domains/instances on the virtualization hosts.
2. Discover all network interfaces and attached drives.
3. Report CPU Usage, Memory Usage, Network I/O stats, and drives attached.

Notes:

At the moment, the scripts are written to monitor a cluster (OpenStack in our case) of virtualization hosts. We collect and report data to a pseudo-host. For each domain, an application is created in zabbix that has its monitored parameters.

It will be updated to monitor using zabbix agents.

## Installation requirements

* packages on the OS
`yum install -y openssl-devel libvirt-devel gcc python-devel`

* python packages
`pip install configparser sslpsk py-zabbix libvirt-python`

## Deploy

1. Create a configuration file (see `examples/config.ini`) at `/etc/zabbix-libvirt/`.
2. Create a hosts file (see `examples/hosts.txt`) and put the path to it in the config file.
3. Call `main.py` with whatever frequency your zabbix server can handle. You can setup a cron job.
