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

import queue
import threading
import random


class Client:
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

    #Test-Mode
    test_mode = False
    if len(sys.argv) > 1:
        if (sys.argv[1] == '1'):
            test_mode = True
            logging.info("Test mode active...")
    cycles = 0

    #ACK
    SIGNAL_ACK = b"\x04" #Signals Acknowledgement

    #EOL
    SIGNAL_EOL = b"\x03"  # Signals END OF LINE

    #How long to wait for an event
    REQUEST_TIMEOUT = 2500
    #Number of retries for a message
    REQUEST_RETRIES = 10
    SERVER_ENDPOINT = "tcp://localhost:5555"

    context = zmq.Context()

    #Create a Faker instance and a geo provider for gps data
    fake = Faker()
    fake.add_provider(geo)

    #Dictionary of not confirmed requests
    dictionary_iterator = 0
    not_confirmed_requests = {}
    q_add_counter = 3

    #Sensor Thread and Data Queue configuration
    BUF_SIZE = 10
    q = queue.Queue(BUF_SIZE)

    client = None


    def __init__(self):
        firstSensor = threading.Thread(
                target=self.sensorThread, args=(), name='Sensor 1')
        secondSensor = threading.Thread(
                target=self.sensorThread, args=(), name='Sensor 2')
        pollerThread = threading.Thread(
                        target=self.pollerThread, args=(), name='Poller Thread')

        firstSensor.start()
        secondSensor.start()

        time.sleep(3)

        pollerThread.start()



    def sensorThread(self):
        while True:
            if not self.q.full():
                location = str(self.fake.latitude())+','+str(self.fake.longitude())
                logging.info("(%s) Location is (%s)", threading.currentThread().getName(), location)
                self.q.put(location)
                time.sleep(randint(0, 10))

    def pollerThread(self):
        #Connect to server
        logging.info("Connecting to Server…")
        self.client = self.context.socket(zmq.DEALER)
        self.client.connect(self.SERVER_ENDPOINT)
        while True:
            if not self.q.empty():
                location = self.q.get()
                logging.info('Sending' + location + ' to server')
                message = [str(self.dictionary_iterator).encode(), str(location).encode(), self.SIGNAL_EOL]
                self.client.send_multipart(message)
                self.not_confirmed_requests[self.dictionary_iterator] = (self.dictionary_iterator, location, self.q_add_counter)
                self.dictionary_iterator +=1
            if (self.client.poll(self.REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
                reply = self.client.recv_multipart()
                logging.info("Got a reply from server")
                index_to_remove = []
                if (len(reply) == 4 and reply[-1] == self.SIGNAL_EOL):
                    for i in self.not_confirmed_requests:
                        (index, location, counter) = self.not_confirmed_requests[i]
                        if ((reply[0] == str(index).encode()) and (reply[1] == str(location).encode())):
                            index_to_remove.append(index)
                            #self.not_confirmed_requests.pop(index)
                            logging.info("Temperature (%s) for location (%s)", reply[2].decode(), reply[1].decode())
                            self.client.send_multipart([self.SIGNAL_ACK, reply[0]])
                        else:
                            if (counter > 0):
                                self.not_confirmed_requests[i] = (index, location, counter - 1)
                            else:
                                logging.info("Could not get an acknowledgement for message %d, adding back to queue", index)
                                index_to_remove.append(index)
                                #self.not_confirmed_requests.pop(index)
                                self.q.put(location)
                    for index in index_to_remove:
                        self.not_confirmed_requests.pop(index)
                    continue
                else:
                    logging.info("Malformed reply from server: %s", reply)
                    continue

            logging.warning("No response from server")
            # Socket is confused. Close and remove it.
            self.client.setsockopt(zmq.LINGER, 0)
            self.client.close()


            logging.info("Reconnecting to server…")
            # Create new connection
            self.client = self.context.socket(zmq.REQ)
            self.client.connect(self.SERVER_ENDPOINT)
                
if __name__ == "__main__":
    Client()


