import socket
import threading
import json
import sys
import time
from protocol import Datagram

TIMEOUT = 5  # Timeout is 5 seconds for retransmission

##############
# Main Program
##############

class Daemon:
    def __init__(self, daemon_port, client_port):
        self.daemon_port = daemon_port
        self.client_port = client_port
        self.ip = "127.0.0.1"
        
        self.daemon_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.daemon_socket.bind((self.ip, self.daemon_port))
        
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.bind((self.ip, self.client_port))
        
        self.datagram = Datagram()
        self.sequence_number = 0
        self.client_address = None
        self.client_username = None
        self.current_chat_port = None
        self.waiting_for_response = False
        # Initialize has_turn based on port number to prevent deadlock
        self.has_turn = self.daemon_port < self.client_port  # One daemon starts with turn
        self.last_received_seq = -1  # Track last received sequence number

        self.is_busy = False
    
   
    def send_with_stop_and_wait(self, datagram, target_addr):
        while True:
            self.daemon_socket.sendto(datagram, target_addr)
            start_time = time.time()
            while time.time() - start_time < TIMEOUT:
                if self.waiting_for_response == False:  # Set when ACK is received
                    return  # ACK received, exit
            print("Timeout! Retransmitting...")

    def handle_client_messages(self):
        """
        Function where we handle client messages along with fulfilling the 3-way handshake method.
        """
        while True:
            try:
                data, addr = self.client_socket.recvfrom(1024)
                msg = json.loads(data.decode())
                
                if data:
                    if msg['type'] == 'connect':
                        self.client_address = addr
                        self.client_username = msg['username']
                        self.client_socket.sendto(json.dumps({
                            'type': 'connected',
                            'message': 'Connected to daemon'
                        }).encode(), addr)
                    
                    elif msg['type'] == 'start_chat':
                        target_port = int(msg['target_port'])

                        # Send SYN to start three-way handshake
                        datagram = self.datagram.create_datagram(
                            0x01,  # Control datagram
                            0x02,  # SYN
                            self.sequence_number,
                            self.client_username,
                            ""
                        )
                        self.send_with_stop_and_wait(datagram, (self.ip, target_port))
                        self.waiting_for_response = True
                        self.current_chat_port = target_port
                    
                    elif msg['type'] == 'chat_response':
                        if msg['accept']:
                            # Send SYN+ACK
                            datagram = self.datagram.create_datagram(
                                0x01,  # Control datagram
                                0x06,  # SYN+ACK because of bitwise or 0x02 │ 0x04 = 0x06
                                self.sequence_number,
                                self.client_username,
                                ""
                            )
                            self.send_with_stop_and_wait(datagram, (self.ip, self.current_chat_port))
                        else:
                            # Send FIN
                            datagram = self.datagram.create_datagram(
                                0x01,  # Control datagram
                                0x08,  # FIN
                                self.sequence_number,
                                self.client_username,
                                ""
                            )
                            self.send_with_stop_and_wait(datagram, (self.ip, self.current_chat_port))
                            self.current_chat_port = None
                    
                    elif msg['type'] == 'chat_message':
                        # Check if it's the current daemon's turn
                        if self.has_turn and self.current_chat_port:
                            self.sequence_number += 1
                            datagram = self.datagram.create_datagram(
                                0x02,  # Chat datagram
                                0x01,  # Fixed for chat
                                self.sequence_number,
                                self.client_username,
                                msg['message']
                            )
                            self.send_with_stop_and_wait(datagram, (self.ip, self.current_chat_port))
                            self.has_turn = False  # Reset turn until ACK is received
                        else:
                            # Notify the client it's not their turn
                            self.client_socket.sendto(json.dumps({
                                'type': 'error',
                                'message': 'Not your turn'
                            }).encode(), self.client_address)
                            
                    elif msg['type'] == 'quit':
                        if self.current_chat_port:
                            datagram = self.datagram.create_datagram(
                                0x01,  # Control datagram
                                0x08,  # FIN
                                self.sequence_number,
                                self.client_username,
                                ""
                            )
                            self.send_with_stop_and_wait(datagram, (self.ip, self.current_chat_port))
                            self.current_chat_port = None

            except Exception as e:
                print(f"Error message from client: {e}")
                break

    def handle_daemon_messages(self):
        while True:
            try:
                data, addr = self.daemon_socket.recvfrom(1024)
                header_info = self.datagram.parse_datagram(data)
                msg_type, operation, seq_num, username, _, payload = header_info

                if msg_type == 0x01:  # Control datagram
                    if operation == 0x02:  # SYN
                        if self.is_busy or self.current_chat_port:
                            datagram = self.datagram.create_datagram(
                                0x01, #Control Datagram
                                0x08, # FIN
                                seq_num,
                                self.client_username,
                                ""
                                )
                            self.daemon_socket.sendto(datagram, addr) 

                        else:
                            # ONLY notify client of chat request if daemon is not busy
                            self.current_chat_port = addr[1]
                            if self.client_address:
                                self.client_socket.sendto(json.dumps({
                                    'type': 'chat_request',
                                    'from': username,
                                    'port': addr[1]
                                }).encode(), self.client_address)
                    
                    elif operation == 0x06:  # SYN+ACK
                        self.is_busy = True
                        # Send final ACK
                        datagram = self.datagram.create_datagram(
                            0x01,  # Control datagram
                            0x04,  # ACK
                            seq_num,
                            self.client_username,
                            ""
                        )
                        self.daemon_socket.sendto(datagram, addr)
                        if self.client_address:
                            self.client_socket.sendto(json.dumps({
                                'type': 'chat_started',
                                'with': username
                            }).encode(), self.client_address)
                            
                    
                    elif operation == 0x04:  # ACK
                        if seq_num == self.sequence_number:
                            self.waiting_for_response = False
                            if self.client_address:
                                self.client_socket.sendto(json.dumps({
                                    'type': 'message_ack'
                                }).encode(), self.client_address)
                                
                    
                    elif operation == 0x08:  # FIN
                        # Send ACK for FIN
                        self.is_busy = False
                        datagram = self.datagram.create_datagram(
                            0x01,  # Control datagram
                            0x04,  # ACK
                            seq_num,
                            self.client_username,
                            ""
                        )
                        
                        self.daemon_socket.sendto(datagram, addr)
                        self.current_chat_port = None
                        if self.client_address:
                            self.client_socket.sendto(json.dumps({
                                'type': 'chat_ended'
                            }).encode(), self.client_address)

                elif msg_type == 0x02:  # Chat datagram
                    # Send ACK
                    datagram = self.datagram.create_datagram(
                        0x01,  # Control datagram
                        0x04,  # ACK
                        seq_num,
                        self.client_username,
                        ""
                    )
                    self.daemon_socket.sendto(datagram, addr)

                    # Process message only if it's coming with  a new sequence number
                    if seq_num != self.last_received_seq:
                        self.last_received_seq = seq_num
                        self.has_turn = True  # Set turn to the sender
                        
                        # Forward the message to client
                        if self.client_address:
                            self.client_socket.sendto(json.dumps({
                                'type': 'chat_message',
                                'from': username,
                                'message': payload
                            }).encode(), self.client_address)

            except Exception as e:
                print(f"Error message from daemon: {e}")

    def run(self):
        """
        Function that creates and runs the daemon and client threads
        """
        print(f"Daemon running on {self.ip}")
        print(f"Listening to daemons on port {self.daemon_port}")
        print(f"Listening to clients on port {self.client_port}")
        
        daemon_thread = threading.Thread(target=self.handle_daemon_messages) 
        client_thread = threading.Thread(target=self.handle_client_messages) 
        
        daemon_thread.start()
        client_thread.start()
        
        try:
            daemon_thread.join()
            client_thread.join()
        finally:   
            pass


if __name__ == "__main__":
    daemon_port = int(input("Enter port for deamon-to-deamon: "))
    client_port = int(input("Enter port for client-to-daemon: "))
    daemon = Daemon(daemon_port, client_port)
    if len(sys.argv) == 2:                   #  default: 127.0.0.1
        daemon.ip = sys.argv[1]              # take IP address of deamon as command line parameter
    daemon.run()