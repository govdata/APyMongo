import json

import tornado.web

import apymongo 
from apymongo import json_util

import base


class FindOneHandler(tornado.web.RequestHandler):
    """
       finds a single record
    """

    @tornado.web.asynchronous
    def get(self):     
        conn = apymongo.Connection()
        coll = conn['testdb']['testcollection']
        coll.find_one(callback=self.handle)
        

    def handle(self,response):
        self.write(json.dumps(response,default=json_util.default))
        self.finish()
               

if __name__ == "__main__":
    base.main(FindOneHandler)

  
  
          
        
