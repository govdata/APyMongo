import os
import json

import tornado.web
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.autoreload
from tornado.options import define, options


define("port", default=8000, help="run on the given port", type=int)


class App(tornado.web.Application):
    def __init__(self,ioloop,handler):
        handlers = [(r"/", handler)]
        settings = dict(debug=True,io_loop=ioloop)
        tornado.web.Application.__init__(self, handlers, **settings)


def main(handler):
    tornado.options.parse_command_line()
    ioloop = tornado.ioloop.IOLoop.instance()
    http_server = tornado.httpserver.HTTPServer(App(ioloop,handler))
    http_server.listen(options.port)
    tornado.autoreload.start()
    ioloop.start()


