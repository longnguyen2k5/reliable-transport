from enum import Enum  
recv_ip = "127.0.0.1"
recv_port = 12345
window_size = 10

class message_type (Enum):
    START = 0 
    END = 1 
    DATA = 2 
    ACK = 3 