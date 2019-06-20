"""Implements the PSK socker wrapper for zabbixsender to use"""

import ssl
import sslpsk


class PyZabbixPSKSocketWrapper:
    """Implements ssl.wrap_socket with PSK instead of certificates.

    Proxies calls to a `socket` instance.

    Thanks to @KostyaEsmukov for writing this.
    See the comment and full example here:
    https://github.com/adubkov/py-zabbix/issues/114#issue-430052782
    """

    def __init__(self, sock, identity, psk):
        self.__sock = sock
        self.__identity = identity
        self.__psk = psk

    def connect(self, *args, **kwargs):
        # `sslpsk.wrap_socket` must be called *after* socket.connect,
        # while the `ssl.wrap_socket` must be called *before* socket.connect.
        self.__sock.connect(*args, **kwargs)

        # `sslv3 alert bad record mac` exception means incorrect PSK
        self.__sock = sslpsk.wrap_socket(
            self.__sock,
            # https://github.com/zabbix/zabbix/blob/f0a1ad397e5653238638cd1a65a25ff78c6809bb/src/libs/zbxcrypto/tls.c#L3231
            ssl_version=ssl.PROTOCOL_TLSv1_2,
            # https://github.com/zabbix/zabbix/blob/f0a1ad397e5653238638cd1a65a25ff78c6809bb/src/libs/zbxcrypto/tls.c#L3179
            ciphers="PSK-AES128-CBC-SHA",
            psk=(self.__psk, self.__identity),)

    def __getattr__(self, name):
        return getattr(self.__sock, name)
