#########################################################
#
# A function to close ports / sockets
#
# Version 01: 17 April 2019
#   First pass
#
# Version 02:
#   Return codes:
#   1 => error closing input ports
#   2 => error closing output ports
#   3 => error closing input and output ports
#
# Version 03: 18 April 2019
#   Only needs to work with list of input sockets
#
#########################################################

import socket
from port_opener import port_opener

# import sys


def port_closer(socket_list):

    for a_socket in socket_list:
        try:
            name = a_socket.getsockname()
            a_socket.close()

            print("Closed socket / port, ", a_socket, "/", name)

        except (Exception):
            return 1

    return 0


if __name__ == "__main__":

    # open input ports
    input_ports = (3001, 4001, 5001)
    socket_list = port_opener(input_ports)
    print(socket_list)

    # input ports
    port_closer(socket_list)