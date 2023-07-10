# Prototyping Assignment Documentation 
#### Danila Ferents, Ensar Yakup Evli 
---
### Requirements
1. Application must comprise a local component that runs on your own machine, and a component running in the Cloud
2. Your local component must collect and make use of (simulated) environmental information. For this purpose, design and use a minimum of two virtual sensors that continuously generate realistic data.
3. Data has to be transmitted regularly (multiple times a minute) between the local component and the Cloud component in both directions.
4. When disconnected and/or crashed, the local and Cloud component have to keep working while preserving data for later transmission. Upon reconnection, the queued data needs to be delivered.
---
### Code documentation
We decided to implement Paranoid Pirate Pattern in Python with the help of ZeroMQ library.
![](resources/PPP.png)
As a scenario we decided to have edge temperature devices (smart watches for example) that send messages to server with their location and get reply with exact weather forecast temperature. 
#### Client 
We used Faker library to generate locations (latitude and longtitude) on the client side. 
Then client is sending a request. To ensure that client got all data back we add end of line signal as a last frame, otherwise we repeate request. Default number of repeats (REQUEST_RETRIES) is set to 3, however, can be easily changed. If message is successfully received, then we send acknowledgement signal back to the server to overcome possible crash in the queue problem.   
### Queue 
Queue component is used as a proxy between client and worker server and stands for storing requests in terms of disconnections. As you can see on the figure, clients and queue communicate with REQ/ROUTER pattern. This is made to be able to receive requests from several devices. 
### Worker 
Worker is responsible for getting temperature for the given location and send reply back. It saves requests with no acknowlegment and repeats sending reply within a timeout. 
### References 
1. Faker library
https://fakerjs.dev
2. Chapter 3 - Advanced Request-Reply Patterns https://zguide.zeromq.org/docs/chapter3/#advanced-request-reply
3. Chapter 4 - Reliable Request-Reply Patterns
https://zguide.zeromq.org/docs/chapter4/
