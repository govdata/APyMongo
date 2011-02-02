import json

import tornado.web

import apymongo 
from apymongo import json_util

import base


class FindHandler(tornado.web.RequestHandler):
    """
        Returns all records in the testdb.testcollection collection.
        
        Notice the use of the "loop" method. 
    """

    @tornado.web.asynchronous
    def get(self):     
        conn = apymongo.Connection()
        coll = conn['testdb']['testcollection']
        cursor = coll.find(callback=self.handle)
        cursor.loop()
        

    def handle(self,response):
        self.write(json.dumps(response,default=json_util.default))
        self.finish()
              

if __name__ == "__main__":
    base.main(FindHandler)

  
  
          
     