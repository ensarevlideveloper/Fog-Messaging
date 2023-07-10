from random import randint
import time
import logging
import sys

import zmq

#Fake library for data generation
from faker import Faker

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)


#Test-Mode
test_mode = False

if len(sys.argv) > 1:
    if (sys.argv[1] == '1'):
        test_mode = True
        logging.info("Test mode active...")

HEARTBEAT_LIVENESS = 3
HEARTBEAT_INTERVAL = 1
INTERVAL_INIT = 1
INTERVAL_MAX = 32
ACK_RETRIES = 3
ACK_TIMEOUT = 5

#  Paranoid Pirate Protocol constants
PPP_READY = b"\x01"      # Signals worker is ready
PPP_HEARTBEAT = b"\x02"  # Signals worker heartbeat
SIGNAL_ACK = b"\x04" #Signals Acknowledgement

#EOL
SIGNAL_EOL = b"\x03"  # Signals END OF LINE

def worker_socket(context, poller):
    """Helper function that returns a new configured socket
       connected to the Paranoid Pirate queue"""
    worker = context.socket(zmq.DEALER) # DEALER
    identity = b"%04X-%04X" % (randint(0, 0x10000), randint(0, 0x10000))
    worker.setsockopt(zmq.IDENTITY, identity)
    poller.register(worker, zmq.POLLIN)
    worker.connect("tcp://localhost:5556")
    worker.send(PPP_READY)
    return worker

fake = Faker()

context = zmq.Context(1)
poller = zmq.Poller()

liveness = HEARTBEAT_LIVENESS
interval = INTERVAL_INIT

heartbeat_at = time.time() + HEARTBEAT_INTERVAL

worker = worker_socket(context, poller)
cycles = 0
not_confirmed_requests = {}
while True:
    socks = dict(poller.poll(HEARTBEAT_INTERVAL * 1000))

    for request_addrs in not_confirmed_requests:
        (retries, old_timestamp, frames) = not_confirmed_requests[request_addrs]
        if (time.time() - old_timestamp > ACK_TIMEOUT) and (retries < ACK_RETRIES):
            logging.info("Retrying reply for (%s), (%s)d time", request_addrs, str(retries))
            not_confirmed_requests[request_addrs] = (retries + 1, time.time(), frames)
            worker.send_multipart(frames)

    # Handle worker activity on backend
    if socks.get(worker) == zmq.POLLIN:
        #  Get message
        #  - 3-part envelope + content -> request
        #  - 1-part HEARTBEAT -> heartbeat
        frames = worker.recv_multipart()
        if not frames:
            break # Interrupted

        if len(frames) == 3:
            if (test_mode == True):
                # Simulate various problems, after a few cycles
                cycles += 1
                if cycles > 3 and randint(0, 5) == 0:
                    logging.info("I: Simulating a crash")
                    break
                if cycles > 3 and randint(0, 5) == 0:
                    logging.info("I: Simulating CPU overload")
                    time.sleep(5)
            
            address = str(frames[-1].decode())
            logging.info("Client requests temperature for location (%s)", address)
            temperature = fake.random_int(min=-30, max=55)
            frames.append(str(temperature).encode())
            frames.append(SIGNAL_EOL)
            worker.send_multipart(frames)
            not_confirmed_requests[address] = (0, time.time(), frames)
            liveness = HEARTBEAT_LIVENESS
            time.sleep(1)  # Do some heavy work
        elif len(frames) == 1 and frames[0] == PPP_HEARTBEAT:
            logging.info("I: Queue heartbeat")
            liveness = HEARTBEAT_LIVENESS

        elif frames[-2] == SIGNAL_ACK:
            address = frames[-1].decode()
            logging.info("ACK got for ", str(address))
            not_confirmed_requests.pop(address)

        else:
            logging.info("E: Invalid message: %s" % frames)
        interval = INTERVAL_INIT
    else:
        liveness -= 1
        if liveness == 0:
            logging.info("W: Heartbeat failure, can't reach queue")
            logging.info("W: Reconnecting in %0.2fs..." % interval)
            time.sleep(interval)

            if interval < INTERVAL_MAX:
                interval *= 2
            poller.unregister(worker)
            worker.setsockopt(zmq.LINGER, 0)
            worker.close()
            worker = worker_socket(context, poller)
            liveness = HEARTBEAT_LIVENESS
    if time.time() > heartbeat_at:
        heartbeat_at = time.time() + HEARTBEAT_INTERVAL
        logging.info("I: Worker heartbeat")
        worker.send(PPP_HEARTBEAT)


    