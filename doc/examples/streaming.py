import json

import tornado.web

import apymongo 
from apymongo import json_util

import base


class StreamHandler(tornado.web.RequestHandler):
    """
        Streams the results of "find". 
    """


    @tornado.web.asynchronous
    def get(self):     
     
        self.writing = False    
        self.write('[')
        
        conn = apymongo.Connection()
        coll = conn['testdb']['testcollection']
        cursor = coll.find(callback=self.handle,processor = self.stream_processor)      
        cursor.loop()
        

    def handle(self,response):
        self.write(']')
        self.finish()
               
               
    def stream_processor(self,r,collection):
    
		self.write((',' if self.writing else '') + json.dumps(r,default=json_util.default))
		self.flush()
		if not self.writing:
			self.writing = True
			
	    
if __name__ == "__main__":
    base.main(StreamHandler)

  
  
          
        
