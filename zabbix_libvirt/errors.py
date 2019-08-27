"""Exceptions"""


class LibvirtConnectionError(Exception):
    """Error to indicate something went wrong with the LibvirtConnection class"""
    pass


class DomainNotFoundError(Exception):
    """Error to indicate something went wrong with the LibvirtConnection class"""
    pass
