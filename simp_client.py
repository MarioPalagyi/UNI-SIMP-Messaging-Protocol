import socket
import json
import threading
import sys

class Client:
    """
    Class for creating a Client instance, with the attributes: IP, port, socket connection, username and in_chat as a boolean value. 
    Also contains functions to handle messages, show menu, connect with daemon, chat with other client/the other user and run the threads.
    """
    def __init__(self, daemon_port):
        """
        Here all values of the class initialize. IP, socket and port are set forever at initialization, while username and in_chat will change during execution.
        """
        self.daemon_ip = "127.0.0.1"
        self.daemon_port = daemon_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.username = None
        self.in_chat = False

    def handle_messages(self):
        """
        Function for handling incoming messages.
        """
        while True:
            try:
                data, _ = self.socket.recvfrom(1024)
                msg = json.loads(data.decode())

                if self.in_chat == False:
                    if msg['type'] == 'connected':
                        print("\nConnected to daemon")
                        self.show_menu()

                    elif msg['type'] == 'chat_request':
                        print(f"\nIncoming chat request from {msg['from']}")
                        choice = input("Accept chat? (y/n): ")
                        self.socket.sendto(json.dumps({
                            'type': 'chat_response',
                            'accept': choice.lower() == 'y'
                        }).encode(), (self.daemon_ip, self.daemon_port))
                        if choice.lower() == 'y':
                            self.in_chat = True
                            print("Chat started! Type 'quit' to end chat.")

                    elif msg['type'] == 'chat_started':
                        print(f"\nChat started with {msg['with']}!")
                        print("Type 'quit' to end chat.")
                        self.in_chat = True

                    elif msg['type'] == 'chat_message':
                        print(f"\n{msg['from']}: {msg['message']}")

                    elif msg['type'] == 'error':
                        if msg.get('message') == 'Not your turn':
                            print('---\WAIT for your turn to send a message...\n---')

                    elif msg['type'] == 'chat_ended':
                        print("\nChat ended")
                        self.in_chat = False
                        self.show_menu()

                    elif msg['type'] == 'message_ack':
                        print("--- Message delivered ---")
                    
                else:
                    if msg['type'] == 'chat_message':
                        print(f"\n{msg['from']}: {msg['message']}")
                    elif msg['type'] == 'chat_ended':
                        print("\nChat ended")
                        self.in_chat = False
                        self.show_menu()
                    elif msg['type'] == 'message_ack':
                        print('--- Message delivered. ---')
                    elif msg['type'] == 'error':
                        if msg.get('message') == 'Not your turn':
                            print('---\nWait for your turn to send a message...\n---')
                    
                # Handles chat requests while already in a chat
                if self.in_chat and msg['type'] == 'chat_request':
                    self.socket.sendto(json.dumps({
                        'type': 'error',
                        'message': 'User already in another chat'
                    }).encode(), (self.daemon_ip, self.daemon_port))
                    self.socket.sendto(json.dumps({
                        'type': 'chat_ended'
                    }).encode(), (self.daemon_ip, self.daemon_port)) 

            except Exception as e:
                print(f"Error receiving message: {e}")
                break

    def show_menu(self):
        """
        Function for showing the user the options. Also waits for input 
        """
        print("\nOptions:")
        print("1. Start new chat")
        print("2. Wait for chat requests")
        print("q. Quit")
        
        choice = input("Choose an option: ")
        
        if choice == '1':
            target_port = input("Enter target daemon port: ")
            self.socket.sendto(json.dumps({
                'type': 'start_chat',
                'target_port': target_port
            }).encode(), (self.daemon_ip, self.daemon_port))
        
        elif choice == 'q':
            self.socket.sendto(json.dumps({
                'type': 'quit'
            }).encode(), (self.daemon_ip, self.daemon_port))
            print("Goodbye!")
            sys.exit(0)
        
        elif choice not in ['1', '2', 'q']: 
            print("#####\nInvalid option\n#####\n---> Choose from options: 1, 2 or 'q' to quit!")
            self.show_menu()

    def connect(self):
        """
        Function for creating a connection request to the daemon and sending the username.
        """
        self.username = input("Enter your username: ")
        self.socket.sendto(json.dumps({
            'type': 'connect',
            'username': self.username
        }).encode(), (self.daemon_ip, self.daemon_port))

    def chat(self):
        """
        Function where we send chat message to other client or quit the chat.
        """
        while True:
            if self.in_chat:
                message = input()
                if message.lower() == 'q':
                    self.socket.sendto(json.dumps({
                        'type': 'quit'
                    }).encode(), (self.daemon_ip, self.daemon_port))
                    self.in_chat = False
                    self.show_menu()
                else:
                    self.socket.sendto(json.dumps({
                        'type': 'chat_message',
                        'message': message
                    }).encode(), (self.daemon_ip, self.daemon_port))

    def run(self):
        """
        Function for starting the thread for the receiving thread and the chat sending thread.
        """
        self.connect()
        receive_thread = threading.Thread(target=self.handle_messages, daemon=True)
        receive_thread.start()
        
        chat_thread = threading.Thread(target=self.chat, daemon=True)
        chat_thread.start()
        
        while True:
            try:
                pass
            except KeyboardInterrupt:
                print("\nDisconnecting...")
                sys.exit(0)

if __name__ == "__main__":
    daemon_port = int(input("Enter client-daemon port: "))
    client = Client(daemon_port)
    if len(sys.argv) == 2:                     # default: 127.0.0.1
        client.daemon_ip = sys.argv[1]         # take IP address as command line parameter
    client.run()