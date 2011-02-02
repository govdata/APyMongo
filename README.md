APyMongo
=======
**Info:** A tornado-based asynchronous version of the pymongo driver for MongoDB.

**Author:** Dan Yamins <dyamins@gmail.com>

About
=====

APyMongo is an asynchronous version of [the PyMongo driver for MongoDB](http://api.mongodb.org/python).
APyMongo uses the [tornado iostream eventloop](github.com/facebook/tornado/blob/master/tornado/iostream.py) 
to drive asychronous requests.  A primary use of APyMongo is to serve MongoDB-backed websites in an efficient asynchronous manner
via the [tornado web server](www.tornadoweb.org), but it can be used wherever one wants to drive multiple efficient 
highthrouput read-write connections to a MongoDB instance.   

APyMongo was developed by the [GovData Project](http://web.mit.edu/govdata), 
which is sponsored by the [Institute for Quantitative Social Science at Harvard](http://iq.harvard.edu).


Installation
============

For now, the project is just a github repo (https://github.com/yamins81/apymongo].

The install process is: 

1. install mongodb if you havent already
2. pull the apymongo repo
3. run "python setup.py install" in the apymongo directory.


Dependencies
============

Mongo:  APyMongo works for the same MongoDB distributions that PyMongo works on. 

Python:  APyMongo requires Python >=2.4.    

Tornado:  IMPORTANT!!! You MUST must be using the a recent pull from the Tornado repository to  
run APyMongo.   APyMongo depends on a recent addition to the tornado.iostream module that is NOT
present in the current release. 

Additional dependencies are:

- (to generate documentation) [sphinx](http://sphinx.pocoo.org/)  
- (to auto-discover tests) [nose](http://somethingaboutorange.com/mrl/projects/nose/).


Examples
========
Here's a basic example that can be used in a Tornado web server:

	import json
	import tornado.web
	
	import apymongo 
	from apymongo import json_util
		
	class TestHandler(tornado.web.RequestHandler):
	
		@tornado.web.asynchronous
		def get(self):     
			connection = apymongo.Connection()		
			collection = conn['testdb']['testcollection']
			coll.find_one(callback=self.handle)
			
		def handle(self,response):
			self.write(json.dumps(response,default=json_util.default))
			self.finish()

For more information, see the **examples** section of the docs.  To use a given example:

1. Make sure you have installed mongo and apymongo (and tornado), and that 
a MongoDB instance is running on localhost:27017 (the default).

2. cd /path/to/apymongo/doc/examples

3. python [desired_example_file.py]

4. Open a web broweser and point it to localhost:8000



Documentation
=============

Currently, there is no separate documentation for this project. 

However,  APyMongo's API is essentially identical to pymongo's except for the following:

- Every pymongo method that actually hits the database for a response
now has a *callback* argument, a single-argument executable to which tornado will
pass the contents of the response when it is ready to be read.  In other words, 
you can no longer do e.g.:

    r = collection.find_one()
	
but must instead do e.g.:

    def callback(r):
        #handle response ... 

    collection.find_one(callback)
    
This goes for **ALL** methods that hit the database, including even such ``simple" things as 
connection.database_names.

- Cursors have no *next* method.  Instead, to obtain the equivalent of ``list(cursor.find())",
use the *apymongo.cursor.loop* method.  

- The Connection method has a *io_loop* argument, to which you can pass an existing 
tornado.io_loop object for the streams to attach to.


Testing
=======

The easiest way to run the tests is to install [nose](http://somethingaboutorange.com/mrl/projects/nose/>) via **easy_install
nose**) and run **nosetests** or **python setup.py test** in the root
of the distribution. Tests are located in the *test/* directory.

Currently, the tests are very scant (and -- something using the AsyncTestCase in the tornado.testing framework
is not working quite right ...)


Limitations
===========

APymongo currently does not handle:

- master-slave connections.  
- DBRef derefercing in son manipulators. 
- the *explain* method


Relationship to **asyncmongo**
=============================

APyMongo was developed for the GovData project (https://github.com/yamins81/govdata-core), where a 
version of it is buried deep in the govdata core code.   While APyMongo was being modularized 
for separate relase, we learned of [asyncmongo](https://github.com/bitly/asyncmongo), 
an existing asynchronous python-language MongoDB driver that also uses the tornado iostream. 

Because asyncmongo has a somewhat different API, we decided to release APyMongo as a separate project. 
