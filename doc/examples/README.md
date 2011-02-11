Using these examples
=====================

These examples will start up a little Tornado webserver serving requests that read/write
asynchronously to a MongoDB collection. 

To use a given example:

1. Make sure you have installed MongoDB, Tornado, and of course APyMongo itself.  

2. Ensure that a MongoDB instance is running on localhost:27017, the MongoDB default. 
Also, make sure that no other process is using localhost:8000 on your computer,
as this is the place where there test Tornado webserver will be put.  (If you must
use different ports either for the MongoDB instance of the Tornado server, 
modify the relevant places in "base.py" in this directory.) 

3. Change directory to [APyMongo Source Directory]/doc/examples -- the directory this readme file is in.  
It is important you do this (or, add this directory to your PYTHONPATH).

3. Run this command:   python [desired_example_file.py]

4. Open a web browser and point it to localhost:8000