import argparse
import socket
import sys
import config
from utils import PacketHeader, compute_checksum

def send_ack(sock, addr, seq_num):
    ack = PacketHeader(type=config.message_type.ACK, seq_num=seq_num, length=0, checksum=0)
    ack.checksum = compute_checksum(ack)
    sock.sendto(bytes(ack), addr)

def receiver(ip, port, window_size):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))

    expected_seq = 1
    received_data = {}
    buffer = {}
    is_running = False

    while True:
        pkt_bytes, addr = sock.recvfrom(2048)

        if len(pkt_bytes) < 16:
            continue

        pkt = PacketHeader(pkt_bytes[:16])
        payload = pkt_bytes[16:16 + pkt.length]

        original_checksum = pkt.checksum
        pkt.checksum = 0
        if compute_checksum(pkt / payload) != original_checksum:
            continue  # Drop corrupted packet

        if pkt.type == config.message_type.START and pkt.seq_num == 0:
            # START packet
            is_running = True
            expected_seq = 1
            received_data.clear()
            buffer.clear()
            send_ack(sock, addr, 1)

        elif pkt.type == config.message_type.DATA and is_running:
            # DATA packet
            if pkt.seq_num >= expected_seq + window_size:
                continue  # Outside window

            if pkt.seq_num < expected_seq:
                send_ack(sock, addr, expected_seq)
                continue

            if pkt.seq_num not in received_data:
                received_data[pkt.seq_num] = payload

            while expected_seq in received_data:
                buffer[expected_seq] = received_data[expected_seq]
                del received_data[expected_seq]
                expected_seq += 1

            send_ack(sock, addr, expected_seq)

        elif pkt.type == config.message_type.END and is_running:
            # END packet
            send_ack(sock, addr, pkt.seq_num + 1)
            break

    for seq in sorted(buffer):
        sys.stdout.buffer.write(buffer[seq])
    sys.stdout.flush()
    sock.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip")
    parser.add_argument("receiver_port", type=int)
    parser.add_argument("window_size", type=int)
    args = parser.parse_args()
    receiver(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()