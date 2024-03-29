from socket import AF_INET
from typing import List, NamedTuple, Union

from routeentry import RouteEntry
from routerbase import logger
from routingtable import RoutingTable
from validate_data import INFINITY

MAX_ENTRIES = 25
ENTRY_LEN = 20
HEADER_LEN = 4
RIP_PACKET_COMMAND = 2
RIP_VERSION_NUMBER = 2


class ResponseEntry(NamedTuple):
    afi: int
    router_id: int
    metric: int


class ResponsePacket(NamedTuple):
    command: int
    version: int
    sender_router_id: int
    entries: List[ResponseEntry]


def get_next_packet_entries(table: RoutingTable, dest_router_id: int):
    """
    Gets the entries from the routing table, which can be sent to the given
    `router_id`. Entries which have a metric of less than infinity, or have a
    flag, and are not learned from the router to whom the packets are going to
    be sent to are added to the yielded list of entries.

    Keyword arguments:
    table -- The routing table, containing all of the entries.
    router_id -- The router the packet is being sent to.
    """
    entries = []
    for current_router_id in table:
        route: RouteEntry = table[current_router_id]
        if route.next_hop == dest_router_id:
            route = route.shallow_copy()
            route.metric = INFINITY

        entries.append((current_router_id, route))
        if len(entries) == MAX_ENTRIES:
            yield entries
            entries = []
    yield entries


def _construct_packet_header(packet: bytearray, table) -> None:
    """
    Modifies the packet's header.

    Keyword arguments:
    packet -- The packet who will have its header populated.
    table -- The table from whom the packet is going to be sent from.
    """
    # the following are implicitly converted to bytes
    packet[0] = RIP_PACKET_COMMAND
    packet[1] = RIP_VERSION_NUMBER
    packet[2:4] = table.router_id.to_bytes(2, "big")


def _construct_packet(table: RoutingTable, entries) -> bytearray:
    """
    Constructs an individual packet, with up to 25 entries inside, with the
    given table entries.
    """
    packet = bytearray(HEADER_LEN + len(entries) * ENTRY_LEN)
    _construct_packet_header(packet, table)
    current_index = 4

    for (destination_router_id, entry) in entries:
        packet[current_index : current_index + 2] = AF_INET.to_bytes(2, "big")
        packet[
            current_index + 4 : current_index + 8
        ] = destination_router_id.to_bytes(4, "big")
        packet[
            current_index + 16 : current_index + ENTRY_LEN
        ] = entry.metric.to_bytes(4, "big")
        current_index += ENTRY_LEN

    return packet


def construct_packets(table: RoutingTable, router_id: int) -> List[bytearray]:
    """Constructs packets to send to a `router_id`, from the routing table."""
    packets: List[bytearray] = []

    for entries in get_next_packet_entries(table, router_id):
        packets.append(_construct_packet(table, entries))

    return packets


def _read_packet_entry(packet: Union[bytearray, bytes], start_index: int) -> ResponseEntry:
    """
    Returns the properties of a single RIP entry inside a RIP response packet.
    """
    afi = int.from_bytes(packet[start_index : start_index + 2], byteorder="big")
    router_id = int.from_bytes(
        packet[start_index + 4 : start_index + 8], byteorder="big"
    )
    metric = int.from_bytes(
        packet[start_index + 16 : start_index + 20], byteorder="big"
    )
    return ResponseEntry(afi, router_id, metric)


def read_packet(packet: Union[bytearray, bytes]) -> ResponsePacket:
    """Returns the properties of the received RIP response packet."""
    command: int = packet[0]
    version: int = packet[1]
    sender_router_id: int = int.from_bytes(packet[2:4], byteorder="big")

    entries = []
    start_index = HEADER_LEN

    while start_index < len(packet):
        end_index = start_index + ENTRY_LEN
        if end_index <= len(packet) and len(entries) < MAX_ENTRIES:
            entries.append(_read_packet_entry(packet, start_index))
        else:
            return ResponsePacket(command, version, sender_router_id, entries)
        start_index = end_index
    return ResponsePacket(command, version, sender_router_id, entries)


def validate_packet(table: RoutingTable, packet: ResponsePacket):
    """
    Returns a Boolean indicating whether the given packet is valid.
    """
    # Checks whether the router_id belongs to the router itself
    if table.router_id == packet.sender_router_id:
        logger(
            f"The packet's router_id of {packet.sender_router_id} illegally "
            + "matches the router_id of this router.",
            is_debug=True,
        )
        return False

    # Checks whether the router_id is from a valid neighbour
    if packet.sender_router_id not in table.neighbours():
        logger(
            f"Packet received from router_id {packet.sender_router_id}, which "
            "is not a neighbour of this router.",
            is_debug=True,
        )
        logger(
            f"Current neighbours of this router {table.router_id} are "
            f"{[i for i in table.neighbours()]}.",
            is_debug=True,
        )
        return False

    # Checks that the command is valid
    if packet.command != 2:
        logger(
            f"The packet has a command value of {packet.command}, instead of 2.",
            is_debug=True,
        )
        return False

    if packet.version != 2:
        logger(
            f"The packet has a version value of {packet.version}, instead of 2.",
            is_debug=True,
        )
        return False

    return True
