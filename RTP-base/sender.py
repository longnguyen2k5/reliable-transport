import argparse
import socket
import config
from utils import PacketHeader, compute_checksum

seq_num = 10

def receive_ACK(s):
    global seq_num
    s.settimeout(0.5)  
    try:
        pkt, address = s.recvfrom(1024)
        ack_header = PacketHeader(pkt[:16])
        if ack_header.seq_num == seq_num:
            print(f"Received ACK for seq_num: {seq_num}")
            seq_num = (seq_num + 1) % 2  
            return True
    except socket.timeout:
        print("Timeout, resending packet...")
    return False

def send(receiver_ip, receiver_port, window_size, message_type, data):
    global seq_num
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    pkt_header = PacketHeader(type=message_type, seq_num=seq_num, length= len(data))
    pkt_header.checksum = compute_checksum(pkt_header / data)
    pkt = pkt_header / data
    
    s.sendto(bytes(pkt), (receiver_ip, receiver_port))
    print(f"Sent packet with seq_num: {seq_num}")
    
    receive_ACK(s)

if __name__ == "__main__":
    """SEND START MESSAGE"""
    send(receiver_ip=config.recv_ip, receiver_port=config.recv_port, message_type=2, window_size=config.window_size, data="hihi\0")
    """SEND DATA"""
