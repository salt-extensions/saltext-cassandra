"""
Salt returner module
"""

import logging

log = logging.getLogger(__name__)

__virtualname__ = "cassandra"


def __virtual__():
    # To force a module not to load return something like:
    #   return (False, "The cassandra returner module is not implemented yet")
    return __virtualname__
