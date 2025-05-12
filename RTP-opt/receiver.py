import argparse
import socket
import sys
import time
import config 
from utils import PacketHeader, compute_checksum

# Global variables
expected_seq = 0  # The next expected sequence number
buffer = {}  # Buffer for out-of-order packets
in_connection = False  # Flag to track if we're in an active connection
is_running = True 
last_ack_time = 0  # Time of last ACK sent
ack_interval = 0.1  # Send ACK every 0.1 seconds to improve performance

def send_ACK(sock, seq_num, addr):
    """Send ACK with the given sequence number to the specified address"""
    pkt_header = PacketHeader(type=config.message_type.ACK, seq_num=seq_num, length=0)
    pkt_header.checksum = 0
    checksum = compute_checksum(bytes(pkt_header))
    pkt_header.checksum = checksum
    sock.sendto(bytes(pkt_header), addr)
    sys.stdout.flush()

def receiver(receiver_ip, receiver_port, window_size):
    global expected_seq, buffer, in_connection, is_running, last_ack_time
    
    # Create and bind socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))
    sys.stdout.flush()
    
    try:
        while is_running:
            try:
                pkt, address = s.recvfrom(2048)
                
                # Parse header
                try:
                    pkt_header = PacketHeader(pkt[:16])
                except Exception as e:
                    continue
                
                # Extract data based on length field
                if pkt_header.length > 0 and len(pkt) >= 16 + pkt_header.length:
                    msg = pkt[16:16 + pkt_header.length]
                else:
                    msg = b''  # Empty message for control packets
                
                # Validate checksum
                received_checksum = pkt_header.checksum
                pkt_header.checksum = 0
                if pkt_header.length > 0:
                    calculated_packet = bytes(pkt_header) + msg
                else:
                    calculated_packet = bytes(pkt_header)
                
                computed_checksum = compute_checksum(calculated_packet)
                
                if received_checksum != computed_checksum:
                    continue
                
                # Process different packet types
                if pkt_header.type == config.message_type.DATA:
                    seq_num = pkt_header.seq_num
                    sys.stdout.flush()
                    
                    # Drop packets outside window
                    if seq_num >= expected_seq + 2 * window_size:
                        send_ACK(s, expected_seq, address)
                        continue
                    
                    # Handle in-order packet
                    if seq_num == expected_seq:
                        print(msg.decode('utf-8'), end="")
                        sys.stdout.flush()
                        expected_seq += 1
                        
                        # Process buffered packets in order
                        while expected_seq in buffer:
                            print(buffer.pop(expected_seq).decode('utf-8'), end="")
                            sys.stdout.flush()
                            expected_seq += 1
                        
                        # Send ACK for the received packet after processing
                        last_ack_time = time.monotonic()
                        send_ACK(s, expected_seq, address)
                    
                    # Buffer out-of-order packet
                    elif seq_num > expected_seq and seq_num < expected_seq + 2* window_size:
                        buffer[seq_num] = msg
                        send_ACK(s, seq_num + 1, address)
                    
                    # Duplicate packet or old packet
                    elif seq_num < expected_seq:
                        send_ACK(s, expected_seq, address)
                
                # Handle END message
                elif pkt_header.type == config.message_type.END:
                    send_ACK(s, pkt_header.seq_num + 1, address)
                    sys.stdout.flush()
                    is_running = False 
                    buffer.clear()
                    break
                
                elif pkt_header.type == config.message_type.START:
                    expected_seq = pkt_header.seq_num + 1
                    send_ACK(s, expected_seq, address)  
                    sys.stdout.flush()

                # Control ACK frequency to improve performance
                if time.monotonic() - last_ack_time > ack_interval:
                    send_ACK(s, expected_seq, address)
                    last_ack_time = time.monotonic()
            
            except Exception as e:
                sys.stdout.flush()
    
    except Exception as e:
        sys.stdout.flush()
    
    finally:
        s.close()
        sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser(description="Reliable UDP Receiver")
    parser.add_argument("recv_ip", type=str, help="Receiver host")
    parser.add_argument("recv_port", type=int, help="Receiver port")
    parser.add_argument("window_size", type=int, help="Window size")
    args = parser.parse_args()
    
    receiver(receiver_ip=args.recv_ip, receiver_port=args.recv_port, window_size=args.window_size)

if __name__ == "__main__":
    main()
