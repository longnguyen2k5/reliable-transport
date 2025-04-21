import argparse
import socket
import sys
import time
import config
from utils import PacketHeader, compute_checksum

TIME_OUT = 0.5

def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(TIME_OUT)

    message = sys.stdin.buffer.read()
    if not message:
        print("Error: No data to send. Please provide input using stdin or `< input.txt`.")
        s.close()
        return

    chunk_size = config.packet_size
    chunks = [message[i:i + chunk_size] for i in range(0, len(message), chunk_size)]
    total_chunks = len(chunks)
    receiver_addr = (receiver_ip, receiver_port)

    # Send START
    start_pkt = PacketHeader(type=config.message_type.START, seq_num=0, length=0, checksum=0)
    start_pkt.checksum = compute_checksum(start_pkt)
    s.sendto(bytes(start_pkt), receiver_addr)

    try:
        data, _ = s.recvfrom(2048)
        ack = PacketHeader(data)
        ack_checksum = ack.checksum
        ack.checksum = 0
        if ack.type != config.message_type.ACK or ack.seq_num != 1 or compute_checksum(ack) != ack_checksum:
            raise Exception("Invalid ACK for START")
    except:
        print("Error: Timeout or invalid ACK for START")
        s.close()
        return

    # Sliding window
    base = 1
    next_seq = 1
    window = {}

    while base <= total_chunks:
        while next_seq < base + window_size and next_seq <= total_chunks:
            payload = chunks[next_seq - 1]
            pkt = PacketHeader(type=config.message_type.DATA, seq_num=next_seq, length=len(payload), checksum=0)
            pkt.checksum = compute_checksum(pkt / payload)
            full_pkt = pkt / payload
            s.sendto(bytes(full_pkt), receiver_addr)
            window[next_seq] = full_pkt
            next_seq += 1

        try:
            data, _ = s.recvfrom(2048)
            ack = PacketHeader(data)
            ack_checksum = ack.checksum
            ack.checksum = 0
            if compute_checksum(ack) != ack_checksum:
                continue
            if ack.type == config.message_type.ACK and ack.seq_num > base:
                base = ack.seq_num
                for seq in list(window):
                    if seq < base:
                        del window[seq]
        except socket.timeout:
            for pkt in window.values():
                s.sendto(bytes(pkt), receiver_addr)

    # Send END
    end_seq = total_chunks + 1
    end_pkt = PacketHeader(type=config.message_type.END, seq_num=end_seq, length=0, checksum=0)
    end_pkt.checksum = compute_checksum(end_pkt)
    s.sendto(bytes(end_pkt), receiver_addr)

    start_time = time.time()
    while time.time() - start_time < TIME_OUT:
        try:
            data, _ = s.recvfrom(2048)
            ack = PacketHeader(data)
            ack_checksum = ack.checksum
            ack.checksum = 0
            if ack.type == config.message_type.ACK and ack.seq_num == end_seq + 1 and compute_checksum(ack) == ack_checksum:
                print("Received ACK for END")
                break
        except:
            continue

    s.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip")
    parser.add_argument("receiver_port", type=int)
    parser.add_argument("window_size", type=int)
    args = parser.parse_args()
    sender(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()