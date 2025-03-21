
import argparse
import socket
import config

from utils import PacketHeader, compute_checksum

def send_ACK (seq_num, addr):
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    pkt_header = PacketHeader(type = config.message_type.ACK,seq_num= seq_num)
    pkt_header.checksum = compute_checksum (pkt_header)
    s.sendto (bytes(pkt_header),addr) 


def receiver(receiver_ip, receiver_port, window_size):
    """TODO: Listen on socket and print received message to sys.stdout."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))
    while True:
        # Receive packet; address includes both IP and port
        pkt, address = s.recvfrom(2048)

        # Extract header and payload
        pkt_header = PacketHeader(pkt[:16])
        msg = pkt[16 : 16 + pkt_header.length]

        # Verity checksum
        pkt_checksum = pkt_header.checksum
        pkt_header.checksum = 0
        computed_checksum = compute_checksum(pkt_header / msg)
        if pkt_checksum != computed_checksum:
            print("checksums not match")
        print(msg.decode("utf-8"))
        send_ACK (seq_num= pkt_header.seq_num,addr= address)
        
def main():
    receiver(receiver_ip=config.recv_ip, receiver_port= config.recv_port, window_size= config.window_size)


if __name__ == "__main__":
    main()
