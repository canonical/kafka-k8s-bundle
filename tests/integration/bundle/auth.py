#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Supporting objects for Kafka user and ACL management."""

import logging
import re
from dataclasses import dataclass
from typing import List, Set

logger = logging.getLogger(__name__)


@dataclass(unsafe_hash=True)
class Acl:
    """Convenience object for representing a Kafka ACL."""

    resource_name: str
    resource_type: str
    operation: str
    username: str


class KafkaAuth:
    """Object for updating Kafka users and ACLs."""

    def __init__(self, charm, opts: List[str], zookeeper: str):
        self.charm = charm
        self.opts = opts
        self.zookeeper = zookeeper
        self.current_acls: Set[Acl] = set()
        self.new_user_acls: Set[Acl] = set()

    @staticmethod
    def _parse_acls(acls: str) -> Set[Acl]:
        """Parses output from raw ACLs provided by the cluster."""
        current_acls = set()
        resource_type, name, user, operation = None, None, None, None
        for line in acls.splitlines():
            resource_search = re.search(r"resourceType=([^\,]+),", line)
            if resource_search:
                resource_type = resource_search[1]

            name_search = re.search(r"name=([^\,]+),", line)
            if name_search:
                name = name_search[1]

            user_search = re.search(r"principal=User\:([^\,]+),", line)
            if user_search:
                user = user_search[1]

            operation_search = re.search(r"operation=([^\,]+),", line)
            if operation_search:
                operation = operation_search[1]
            else:
                continue

            if resource_type and name and user and operation:
                current_acls.add(
                    Acl(
                        resource_type=resource_type,
                        resource_name=name,
                        username=user,
                        operation=operation,
                    )
                )

        return current_acls
