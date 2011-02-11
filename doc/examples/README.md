Using these examples
=====================

These examples will start up a little Tornado webserver serving requests that read/write
asynchronously to a MongoDB collection. 

To use a given example:

1. Make sure you have installed MongoDB, Tornado, and of course APyMongo itself.  

2. Ensure that a MongoDB instance is running on localhost:27017 (the MongoDB default).
Also, make sure that no other process is using localhost:8000 on your computer,
as this is the place where there test Tornado webserver will be put.  If you must use a different port for the MongoDB instance, modify places in the 
example files where the connection object is created, passing your desired port number 
as a keyword argument.  E.g. if MongoDB is running on 9999, do:

    conn = apymongo.Connection(port=9999)

    If you need to put the the Tornado server somewhere else, modify the obviously
relevant place in the file "base.py" in the examples directory. 

3. Change directory to [APyMongo Source Directory]/doc/examples -- the directory this readme file is in. Then run:

    python [desired_example_file.py]

4. Open a web browser and point it to localhost:8000