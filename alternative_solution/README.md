
# Prototyping Assignment (Alternative Solution) Documentation 
#### Danila Ferents, Ensar Yakup Evli 
---
### General Information
The solution in this folder of the project represents an alternative solution to our main solution. 
### Reasoning for this solution
* Our first solution didn't need a queue for its use case. We wanted clients to directly communicate with the server. It was based on the following exemplary assumption: Clients are using a smart watch that tracks their location and receives temperatures based on their location. Under this assumption, in case of a server crash the client would not need replies from previous location since it is moving and constantly generating new data.
* After reading the requirements while doing the documentation again, we weren't sure if our scenario meets the expectations of our task. Although we had some thorough discussions with our instructors, we wanted to be sure to submit the best possible solution.  Thus, we implemented this solution that may fit better to the requirements depending on the understanding of the tasks.

### Description of changes
This alternative solution is based on the main solution and extends its functionality. Instead of running two seperate clients, this solution runs one client. The client will then start three threads. Two threads to represent sensors. They continously add data to a queue. One thread is the poller thread. It sends and receives data continously. Further, the poller thread uses a dictionary to store messages that did not get a reply yet (similar to the worker in this solution and the main solution). When sending a request for data the poller thread adds this message to the dictionary. The poller thread continously goes through the dictionary. If a reply was received for a request, the according entry is deleted from the dictionary. If a request does not arrive after a specified amount of iterations, the entry is deleted from the dictionary and added to the data queue again. Thus, the message can be sent again since we can assume we have a lost-reply situation.