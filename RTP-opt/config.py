packet_size = 1456 #1500 MTU of ethernet  - 8 UDP_header - 20 IP_header - 16 Packet_Header = 1456 bytes

class message_type:
    START = 0 
    END = 1 
    DATA = 2 
    ACK = 3 