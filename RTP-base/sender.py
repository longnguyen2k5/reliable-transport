import argparse
import socket
import threading
import time
import config
import sys
from utils import PacketHeader, compute_checksum

# Global variables
base = 0  # Base of the sliding window
seq_num = 0  # Sequence number for packets
window = {}  # Store unacknowledged packets
lock = threading.Lock()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
timer = None  # Timer for retransmission
time_stamps = {} # Store timestamp for each packet 
is_running = True  # Flag to control thread execution
end_received = False  # Flag to track if END ACK was received
timeout = 3.5
ws = 0
num_packet = 0

def check_timeout():
    global is_running, timeout
    while is_running:
        current_time = time.monotonic()
        with lock:
            for seq, send_time in list(time_stamps.items()):
                if current_time - send_time > timeout: 
                    if seq in window: 
                        print(f"Timeout! Retransmitting packet {seq}")
                        sys.stdout.flush()
                        s.sendto(window[seq], (config.recv_ip, config.recv_port))
                        time_stamps[seq] = time.monotonic()  
        time.sleep(0.05)  

def receive_ACK():
    global base, timer, is_running, end_received, ws, num_packet
    
    while is_running:
        try:
            s.settimeout(0.1)  # Short timeout to check is_running flag frequently
            pkt, _ = s.recvfrom(1024)
            
            if not is_running:
                break
                
            ack_header = PacketHeader(pkt[:16])
            
            # Check if it's an ACK packet
            if ack_header.type != config.message_type.ACK:
                continue
                
            ack_num = ack_header.seq_num
            print(f"Received ACK: {ack_num}")
            sys.stdout.flush()
            
            with lock:
                if ack_num >= base:
                    #Delete packet [ack_num] in window 
                    window.pop (ack_num-1,None)
                    time_stamps.pop(ack_num-1,None)
                    ws = max (0, ws - 1)
                    #Plus base to slide window
                    while base not in window and base < seq_num:     
                        base += 1 

                    # Handle END message acknowledgment
                    if num_packet + 1 == ack_num:
                        print (f"seq num of END message :{ack_num}")
                        print("All packets including END message acknowledged")
                        sys.stdout.flush()
                        end_received = True
                        is_running = False
                        if timer:
                            timer.cancel()
                        break
        
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error in receive_ACK: {e}")
            sys.stdout.flush()
            
    print("ACK receiver thread exiting")
    sys.stdout.flush()

def send_packet(data, seq):
    global window
    pkt_header = PacketHeader(type=config.message_type.DATA, seq_num=seq, length=len(data))
    
    # Set checksum to 0 before calculating
    pkt_header.checksum = 0
    
    # Create full packet and compute checksum
    full_packet = bytes(pkt_header) + data
    checksum = compute_checksum(full_packet)
    
    # Update header with checksum
    pkt_header.checksum = checksum
    
    # Construct final packet
    packet = bytes(pkt_header) + data
    
    with lock:
        s.sendto(packet, (config.recv_ip, config.recv_port))
        print(f"Sent packet {seq}")
        sys.stdout.flush()
        window[seq] = packet
        time_stamps[seq] = time.monotonic() 

def send_data(data, window_size):
    global seq_num, base, is_running,ws, timeout, num_packet
    
    # Convert string to bytes if needed
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    # Set socket timeout for non-blocking operations
    s.settimeout(0.5)
    
    # Start the ACK receiver thread
    ack_thread = threading.Thread(target=receive_ACK, daemon=True)
    ack_thread.start()

    #Start the check_timeout thread 
    check_time_out = threading.Thread (target=check_timeout, daemon=True)
    check_time_out.start()

    # Split data into chunks
    chunks = []
    for i in range(0, len(data), config.packet_size):
        chunks.append(data[i:min(i + config.packet_size, len(data))])
    
    print(f"Message split into {len(chunks)} chunks")
    sys.stdout.flush()
    num_packet = len (chunks)
    
    # Send all chunks using sliding window
    while base < len(chunks) and is_running:
        # Send as many packets as window size allows
        while ws < window_size and seq_num < len(chunks):
            send_packet(chunks[seq_num], seq_num)
            seq_num += 1
            ws += 1
        
        # Small delay to prevent CPU hogging
        time.sleep(0.01)
    
    print ("Sending data is done !!!")
    # Wait until all packets are acknowledged
    while base < len(chunks) and is_running:
        print(f"Waiting for acknowledgments... base={base}, seq_num={seq_num}")
        sys.stdout.flush()
        time.sleep(0.1)
    
    if is_running:
        # Send END message
        print ("Send end message ...")
        send_end_message()
        
        # Wait for END acknowledgment or timeout
        end_wait_start = time.time()
        while is_running and not end_received and (time.time() - end_wait_start) < timeout:
            time.sleep(0.05)
        
        # Close everything
        is_running = False
        if timer:
            timer.cancel()
    
    # Give ACK thread time to exit
    ack_thread.join(0.5)
    
    # Close socket
    s.close()
    print("Sender terminated")
    sys.stdout.flush()

def send_end_message():
    global timer, seq_num
    
    print("Sending END message")
    sys.stdout.flush()
    
    # Create END packet
    end_header = PacketHeader(type=config.message_type.END, seq_num=seq_num, length=0)
    end_header.checksum = 0
    
    # Compute checksum for END packet
    packet = bytes(end_header)
    checksum = compute_checksum(packet)
    
    # Update header with checksum
    end_header.checksum = checksum
    end_packet = bytes(end_header)
    
    # Send END packet and store it in window
    with lock:
        s.sendto(end_packet, (config.recv_ip, config.recv_port))
        window[seq_num] = end_packet
        print(f"Sent END message with seq_num {seq_num}")
        sys.stdout.flush()
        time_stamps[seq_num] = time.monotonic() 
        # Increment sequence number
        seq_num += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reliable UDP Sender")
    parser.add_argument("-m", "--message", type=str, required=True, help="Message to send")
    parser.add_argument("-w", "--window-size", type=int, default=config.window_size, 
                      help=f"Window size (default: {config.window_size})")
    args = parser.parse_args()
    
    # Print config information
    print(f"Starting sender with window size: {args.window_size}")
    print(f"Receiver IP: {config.recv_ip}, Port: {config.recv_port}")
    sys.stdout.flush()
    
    # Send data with specified window size
    send_data(args.message, args.window_size)