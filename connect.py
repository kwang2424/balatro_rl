import socket
import subprocess
import json
from enum import Enum
# bot.py

class Actions(Enum):
    SELECT_BLIND = 1
    SKIP_BLIND = 2
    PLAY_HAND = 3
    DISCARD_HAND = 4
    END_SHOP = 5
    REROLL_SHOP = 6
    BUY_CARD = 7
    BUY_VOUCHER = 8
    BUY_BOOSTER = 9
    SELECT_BOOSTER_CARD = 10
    SKIP_BOOSTER_PACK = 11
    SELL_JOKER = 12
    USE_CONSUMABLE = 13
    SELL_CONSUMABLE = 14
    REARRANGE_JOKERS = 15
    REARRANGE_CONSUMABLES = 16
    REARRANGE_HAND = 17
    PASS = 18
    START_RUN = 19
    SEND_GAMESTATE = 20


class Connection:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.instance = None

    def connect_to_server(self):
        """
        Connects to the server with the given host and port.
        Returns True if successful, False otherwise.
        """
        try:
            # Create a socket object
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Connect to the server
            self.sock.connect((self.host, self.port))
            
            return True
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return False

    def start_instance(self):
        balatro_exec_path = (
            r"C:\Program Files (x86)\Steam\steamapps\common\Balatro\Balatro.exe"
        )
        self.instance = subprocess.Popen(
            [balatro_exec_path, str(self.bot_port)]
        )

    def send_message(self, message):
        try:
            self.sock.connect()
            msg = bytes(message, "utf-8")
            self.sock.sendto(msg, self.addr)
        except Exception as e:
            print(f"Failed to send message: {e}")
            return False

    def send_action(self, action):
        cmd = self.action_to_cmd(action)
        self.send_message(cmd)

    def receive_message(self):
        try:
            data = self.sock.recv(65536)
            jsondata = json.loads(data)

            if "response" in jsondata:
                print(jsondata["response"])
            return jsondata
        except Exception as e:
            print(f"Failed to receive message: {e}")
            return {}
    
    def action_to_cmd(self, action):
            result = []

            for x in action:
                if isinstance(x, Actions):
                    result.append(x.name)
                elif type(x) is list:
                    result.append(",".join([str(y) for y in x]))
                else:
                    result.append(str(x))

            return "|".join(result)

    def ping(self):
        self.send_message("ping")
        return self.receive_message()

    def close(self):
        if self.instance:
            self.instance.kill()