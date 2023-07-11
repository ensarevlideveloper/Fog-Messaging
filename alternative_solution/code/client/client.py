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

    #Acknowledgement-Byte
    SIGNAL_ACK = b"\x04" #Signals Acknowledgement

    #End of Line-Byte
    SIGNAL_EOL = b"\x03"  # Signals END OF LINE

    #Request timeout to set how long to wait for an event
    REQUEST_TIMEOUT = 2500
    #Number of retries for a message
    REQUEST_RETRIES = 10
    SERVER_ENDPOINT = "tcp://localhost:5555"

    #ZeroMQ Context
    context = zmq.Context()

    #Create a Faker instance and a geo provider for gps data
    fake = Faker()
    fake.add_provider(geo)

    #Dictionary of replies that don't got a reply yet
    dictionary_iterator = 0
    not_confirmed_requests = {}
    q_add_counter = 50

    #Sensor Thread and Data Queue configuration
    BUF_SIZE = 100
    q = queue.Queue(BUF_SIZE)

    client = None


    def __init__(self):
        #Start two sensor threads to generate sensor data and one poller thread to poll for data from server
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
        #Continously put data into the queue
        while True:
            if not self.q.full():
                location = str(self.fake.latitude())+','+str(self.fake.longitude())
                logging.info("(%s) Location is (%s)", threading.currentThread().getName(), location)
                self.q.put(location)
                time.sleep(randint(0, 10))

    def pollerThread(self):
        #Connect to server
        logging.info("Connecting to Server…")
        #Use Dealer to asynchronously send and receive messages
        self.client = self.context.socket(zmq.DEALER)
        self.client.connect(self.SERVER_ENDPOINT)
        while True:
            #Go into client crashes/overloads to test
            if (self.test_mode == True):
                # Simulate various problems, after a few cycles
                self.cycles += 1
                if self.cycles > 5 and randint(0, 5) == 0:
                    logging.info("I: Simulating a crash")
                    break
                if self.cycles > 5 and randint(0, 5) == 0:
                    logging.info("I: Simulating CPU overload")
                    time.sleep(5)
            #Get data from the queue and send it continously        
            if not self.q.empty():
                location = self.q.get()
                logging.info('Sending' + location + ' to server')
                message = [str(self.dictionary_iterator).encode(), str(location).encode(), self.SIGNAL_EOL]
                self.client.send_multipart(message)
                print("Sent message with number: "+str(self.dictionary_iterator))
                self.not_confirmed_requests[self.dictionary_iterator] = (self.dictionary_iterator, location, self.q_add_counter)
                self.dictionary_iterator +=1
            #Receive data and check dictionary for missing replies
            if (self.client.poll(self.REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
                reply = self.client.recv_multipart()
                index_to_remove = []
                if (len(reply) == 4 and reply[-1] == self.SIGNAL_EOL):
                    for i in self.not_confirmed_requests:
                        (index, location, counter) = self.not_confirmed_requests[i]
                        if ((reply[0] == str(index).encode()) and (reply[1] == str(location).encode())):
                            logging.info("Got a reply for: "+str(index))
                            index_to_remove.append(index)
                            logging.info("Temperature (%s) for location (%s)", reply[2].decode(), reply[1].decode())
                            self.client.send_multipart([self.SIGNAL_ACK, reply[0]])
                        else:
                            if (counter > 0):
                                self.not_confirmed_requests[i] = (index, location, counter - 1)
                            else:
                                logging.info("Could not get an acknowledgement for message %d, adding back to queue", index)
                                index_to_remove.append(index)
                                self.q.put(location)
                    for index in index_to_remove:
                        self.not_confirmed_requests.pop(index)
                    continue
                else:
                    logging.info("Malformed reply from server: %s", reply)
                    continue
                
if __name__ == "__main__":
    Client()


