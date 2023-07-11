from collections import OrderedDict
import time
import logging

import zmq

HEARTBEAT_LIVENESS = 3     # 3..5 is reasonable
HEARTBEAT_INTERVAL = 1.0   # Seconds

#  Paranoid Pirate Protocol constants
PPP_READY = b"\x01"      # Signals worker is ready
PPP_HEARTBEAT = b"\x02"  # Signals worker heartbeat
SIGNAL_ACK = b"\x04" #Signals Acknowledgement

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)


class Worker(object):
    def __init__(self, address):
        self.address = address
        self.expiry = time.time() + HEARTBEAT_INTERVAL * HEARTBEAT_LIVENESS

class WorkerQueue(object):
    def __init__(self):
        self.queue = OrderedDict()

    def ready(self, worker):
        self.queue.pop(worker.address, None)
        self.queue[worker.address] = worker

    def purge(self):
        """Look for & kill expired workers."""
        t = time.time()
        expired = []
        for address, worker in self.queue.items():
            if t > worker.expiry:  # Worker expired
                expired.append(address)
        for address in expired:
            logging.info("W: Idle worker expired: %s" % address)
            self.queue.pop(address, None)

    def next(self):
        address, worker = self.queue.popitem(False)
        return address

context = zmq.Context(1)

frontend = context.socket(zmq.ROUTER) # ROUTER
backend = context.socket(zmq.ROUTER)  # ROUTER
frontend.bind("tcp://*:5555") # For clients
backend.bind("tcp://*:5556")  # For workers

poll_workers = zmq.Poller()
poll_workers.register(backend, zmq.POLLIN)

poll_both = zmq.Poller()
poll_both.register(frontend, zmq.POLLIN)
poll_both.register(backend, zmq.POLLIN)

workers = WorkerQueue()

heartbeat_at = time.time() + HEARTBEAT_INTERVAL

while True:
    if len(workers.queue) > 0:
        poller = poll_both
    else:
        poller = poll_workers
    socks = dict(poller.poll(HEARTBEAT_INTERVAL * 1000))

    # Handle worker activity on backend
    if socks.get(backend) == zmq.POLLIN:
        # Use worker address for LRU routing
        frames = backend.recv_multipart()
        if not frames:
            break

        address = frames[0]
        workers.ready(Worker(address))

        logging.info("Received from server:" + str(frames[0].decode()))

        # Validate control message, or return reply to client
        msg = frames[1:]
        if len(msg) == 1:
            if msg[0] not in (PPP_READY, PPP_HEARTBEAT):
                logging.info("E: Invalid message from worker: %s", msg)
        else:
            logging.info("Sending to client:" + str(frames[0]))
            frontend.send_multipart(msg)

        # Send heartbeats to idle workers if it's time
        if time.time() >= heartbeat_at:
            for worker in workers.queue:
                msg = [worker, PPP_HEARTBEAT]
                backend.send_multipart(msg)
            heartbeat_at = time.time() + HEARTBEAT_INTERVAL
    if socks.get(frontend) == zmq.POLLIN:
        frames = frontend.recv_multipart()
        logging.info("Received from client")
        if not frames:
            break
        #if frames[-2] == SIGNAL_ACK:
        #    frontend.send_multipart(frames)

        frames.insert(0, workers.next())
        logging.info("Sending to worker:"+str(frames[0].decode()))
        backend.send_multipart(frames)


    workers.purge()