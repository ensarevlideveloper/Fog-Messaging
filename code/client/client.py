from random import randint
import itertools
import logging
import sys
#ZeroMQ
import zmq
import time
#Fake library for data generation
from faker import Faker
from faker.providers import geo

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

#Test-Mode
test_mode = False
if len(sys.argv) > 1:
    if (sys.argv[1] == '1'):
        test_mode = True
        logging.info("Test mode active...")

#ACK
SIGNAL_ACK = b"\x04" #Signals Acknowledgement

#EOL
SIGNAL_EOL = b"\x03"  # Signals END OF LINE

#How long to wait for an event
REQUEST_TIMEOUT = 2500
#Number of retries for a message
REQUEST_RETRIES = 3
SERVER_ENDPOINT = "tcp://localhost:5555"

context = zmq.Context()

#Create a Faker instance and a geo provider for gps data
fake = Faker()
fake.add_provider(geo)


logging.info("Connecting to Server…")
client = context.socket(zmq.REQ)
client.connect(SERVER_ENDPOINT)
cycles = 0

for sequence in itertools.count():
    #Create
    location = str(fake.latitude())+','+str(fake.longitude())
    logging.info("Location is (%s)", location)
    request = location.encode()
    logging.info("Sending location")
    client.send(request)

    if (test_mode == True):
        # Simulate various problems, after a few cycles
        cycles += 1
        if cycles > 3 and randint(0, 5) == 0:
            logging.info("I: Simulating a crash")
            break
        if cycles > 3 and randint(0, 5) == 0:
            logging.info("I: Simulating CPU overload")
            time.sleep(5)


     
    retries_left = REQUEST_RETRIES
    while True:
        if (client.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
            reply = client.recv_multipart()
            logging.info("Server replied")
            if reply[0] == request and reply[-1] == SIGNAL_EOL:
                logging.info("Temperature (%s) for location (%s)", reply[-2].decode(), reply[0].decode())
                retries_left = REQUEST_RETRIES

                client.send_multipart([SIGNAL_ACK, reply[0]])
                client.recv_multipart()
                break
            else:
                logging.error("Malformed reply from server: %s", reply)
                continue

        retries_left -= 1
        logging.warning("No response from server")
        # Socket is confused. Close and remove it.
        client.setsockopt(zmq.LINGER, 0)
        client.close()
        if retries_left == 0:
            logging.error("Server seems to be offline, abandoning")
            sys.exit()

        logging.info("Reconnecting to server…")
        # Create new connection
        client = context.socket(zmq.REQ)
        client.connect(SERVER_ENDPOINT)
        logging.info("Resending location")
        client.send(request)