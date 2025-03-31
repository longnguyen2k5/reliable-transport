import argparse
import socket
import sys
import config
from utils import PacketHeader, compute_checksum

# Global variables
expected_seq = 0  # The next expected sequence number
buffer = {}  # Buffer for out-of-order packets
in_connection = False  # Flag to track if we're in an active connection
is_running = True 

def send_ACK(sock, seq_num, addr):
    """Send ACK with the given sequence number to the specified address"""
    pkt_header = PacketHeader(type=config.message_type.ACK, seq_num=seq_num, length=0)
    # Set checksum to 0 before calculating
    pkt_header.checksum = 0
    # Calculate checksum
    checksum = compute_checksum(bytes(pkt_header))
    pkt_header.checksum = checksum
    # Send ACK
    sock.sendto(bytes(pkt_header), addr)
    print(f"Sent ACK {seq_num}")
    sys.stdout.flush()

def receiver(receiver_ip, receiver_port, window_size):
    global expected_seq, buffer, in_connection, is_running
    
    # Create and bind socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))
    print(f"Receiver started on {receiver_ip}:{receiver_port} with window size {window_size}")
    sys.stdout.flush()
    
    try:
        with open("received_message.txt", "wb") as f:
            while is_running:
                try:
                    # Receive packet
                    pkt, address = s.recvfrom(2048)
                    
                    # Parse header
                    try:
                        pkt_header = PacketHeader(pkt[:16])
                    except Exception as e:
                        print(f"Error parsing packet header: {e}")
                        sys.stdout.flush()
                        continue
                    
                    # Extract data based on length field
                    if pkt_header.length > 0 and len(pkt) >= 16 + pkt_header.length:
                        msg = pkt[16:16 + pkt_header.length]
                    else:
                        msg = b''  # Empty message for control packets
                    
                    # Validate checksum
                    received_checksum = pkt_header.checksum
                    pkt_header.checksum = 0
                    
                    # Calculate checksum for validation
                    if pkt_header.length > 0:
                        calculated_packet = bytes(pkt_header) + msg
                    else:
                        calculated_packet = bytes(pkt_header)
                    
                    computed_checksum = compute_checksum(calculated_packet)
                    
                    if received_checksum != computed_checksum:
                        print(f"Checksum mismatch for packet {pkt_header.seq_num}. Received: {received_checksum}, Computed: {computed_checksum}")
                        print("Dropping packet")
                        sys.stdout.flush()
                        continue
                    
                    # Process different packet types
                    if pkt_header.type == config.message_type.DATA:
                        seq_num = pkt_header.seq_num
                        print(f"Received DATA packet with seq_num {seq_num}, expected {expected_seq}")
                        sys.stdout.flush()
                        
                        # Drop packets outside window
                        if seq_num >= expected_seq + window_size:
                            print(f"Packet {seq_num} is outside window, dropping")
                            sys.stdout.flush()
                            send_ACK(s, expected_seq, address)
                            continue
                        
                        # Handle in-order packet
                        if seq_num == expected_seq:
                            print(f"Writing in-order packet {seq_num}")
                            sys.stdout.flush()
                            f.write(msg)
                            expected_seq += 1
                            
                            # Process buffered packets in order
                            while expected_seq in buffer:
                                print(f"Writing buffered packet {expected_seq}")
                                sys.stdout.flush()
                                f.write(buffer.pop(expected_seq))
                                expected_seq += 1
                            
                            print(f"Updated expected_seq to {expected_seq}")
                            sys.stdout.flush()
                            send_ACK(s, expected_seq, address)
                        
                        # Buffer out-of-order packet
                        elif seq_num > expected_seq and seq_num < expected_seq + window_size:
                            print(f"Buffering out-of-order packet {seq_num}")
                            sys.stdout.flush()
                            buffer[seq_num] = msg
                            send_ACK(s, seq_num + 1, address)
                        
                        # Duplicate packet or old packet
                        elif seq_num < expected_seq:
                            print(f"Duplicate or old packet {seq_num}, sending ACK {expected_seq}")
                            sys.stdout.flush()
                            send_ACK(s, expected_seq, address)
                    
                    # Handle END message
                    elif pkt_header.type == config.message_type.END:
                        print(f"Received END message with seq_num {pkt_header.seq_num}")
                        sys.stdout.flush()
                        
                        # Send ACK for END message
                        send_ACK(s, pkt_header.seq_num + 1, address)
                        
                        # Write any remaining buffered packets
                        sorted_keys = sorted(buffer.keys())
                        for key in sorted_keys:
                            if key < pkt_header.seq_num:  # Only write packets before END
                                f.write(buffer[key])
                        
                        print("Connection ended, exiting...")
                        sys.stdout.flush()
                        f.flush()  # Ensure all data is written
                        is_running = False 
                        buffer.clear()
                        break
                    
                    # Handle other message types if needed
                    else:
                        print(f"Received packet with type {pkt_header.type}")
                        sys.stdout.flush()
                
                except Exception as e:
                    print(f"Error processing packet: {e}")
                    sys.stdout.flush()
    
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.stdout.flush()
    
    finally:
        s.close()
        print("Receiver terminated")
        sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser(description="Reliable UDP Receiver")
    parser.add_argument("-w", "--window-size", type=int, default=config.window_size, 
                        help=f"Window size (default: {config.window_size})")
    parser.add_argument("-ip", "--ip", type=str, default=config.recv_ip,
                        help=f"Receiver IP (default: {config.recv_ip})")
    parser.add_argument("-p", "--port", type=int, default=config.recv_port,
                        help=f"Receiver port (default: {config.recv_port})")
    args = parser.parse_args()
    
    receiver(receiver_ip=args.ip, receiver_port=args.port, window_size=args.window_size)

if __name__ == "__main__":
    main()