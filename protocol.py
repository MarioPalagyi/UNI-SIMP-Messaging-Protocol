class Datagram:
    def __init__(self):
        self.MAX_USERNAME_LENGTH = 32               # Maximum byte length for the username field
    
    def _int_to_bytes(self, number):                # Converts integer to 1-byte with big endian
        return number.to_bytes(1, byteorder='big')
    
    def create_datagram(self, msg_type, operation, seq_num, username, message):

        type_byte = self._int_to_bytes(msg_type)    # 1-byte message type (control=0x01, chat=0x02)
        op_byte = self._int_to_bytes(operation)     # 1-byte operation (i.e. SYN=0x02, ACK=0x04...)
        seq_byte = self._int_to_bytes(seq_num)      # 1-byte sequence number (i.e. 0/1)
        
        if len(username) > self.MAX_USERNAME_LENGTH:    # if username too long, take the first 32 bytes
            username = username[:self.MAX_USERNAME_LENGTH]

        username_bytes = username.encode('ascii')       # Convert username to ASCII
        padding = bytes(self.MAX_USERNAME_LENGTH - len(username_bytes))
        username_field = username_bytes + padding       # Add padding to ensure fixed size of 32 bytes
        
      
        payload_bytes = message.encode('ascii')                          # payload (actual message) encoded in ASCII
        payload_len = len(payload_bytes).to_bytes(4, byteorder='big')    # length of the payload (4-byte)
        
       
        return type_byte + op_byte + seq_byte + username_field + payload_len + payload_bytes   # combining all fields (into an bytearray)
    
    def parse_datagram(self, datagram):                # Extract individual fields from the byte array 
        msg_type = datagram[0]
        operation = datagram[1]
        seq_num = datagram[2]
        
        user = datagram[3:35]                          # Extract and decode the username field (up to the first null byte)
        username = ""
        for byte in user:
            if byte == 0:  # Stop at the null byte  
                break
            username += bytes([byte]).decode('ascii')  # Convert the byte to a string
        
        payload_len = int.from_bytes(datagram[35:39], byteorder='big')          # Extract and decode the payload length
        payload = datagram[39:39+payload_len].decode('ascii')
        
        return (msg_type, operation, seq_num, username, payload_len, payload)   # return all fields in a tuple
