# Copyright 2009-2010 10gen, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test the connection module."""

import datetime
import os
import sys
import time
import unittest
import warnings
sys.path[0:0] = [""]

from nose.plugins.skip import SkipTest

from tornado.testing import AsyncTestCase

from bson.son import SON
from bson.tz_util import utc
from apymongo.connection import (Connection,
                                _parse_uri)
from apymongo.database import Database
from apymongo.errors import (AutoReconnect,
                            ConfigurationError,
                            ConnectionFailure,
                            InvalidName,
                            InvalidURI,
                            OperationFailure)
from test import version


def get_connection(*args, **kwargs):
    host = os.environ.get("DB_IP", "localhost")
    port = int(os.environ.get("DB_PORT", 27017))
    return Connection(host, port, *args, **kwargs)


class TestConnection(unittest.TestCase):

    def setUp(self):
        self.host = os.environ.get("DB_IP", "localhost")
        self.port = int(os.environ.get("DB_PORT", 27017))

    def test_types(self):
        self.assertRaises(TypeError, Connection, 1)
        self.assertRaises(TypeError, Connection, 1.14)
        self.assertRaises(TypeError, Connection, "localhost", "27017")
        self.assertRaises(TypeError, Connection, "localhost", 1.14)
        self.assertRaises(TypeError, Connection, "localhost", [])

        self.assertRaises(ConfigurationError, Connection, [])

    def test_constants(self):
        Connection.HOST = self.host
        Connection.PORT = self.port
        self.assert_(Connection())

        Connection.HOST = "somedomainthatdoesntexist.org"
        Connection.PORT = 123456789
        self.assertRaises(ConnectionFailure, Connection)
        self.assert_(Connection(self.host, self.port))

        Connection.HOST = self.host
        Connection.PORT = self.port
        self.assert_(Connection())

    def test_connect(self):
        self.assertRaises(ConnectionFailure, Connection,
                          "somedomainthatdoesntexist.org")
        self.assertRaises(ConnectionFailure, Connection, self.host, 123456789)

        self.assert_(Connection(self.host, self.port))

    def test_host_w_port(self):
        self.assert_(Connection("%s:%d" % (self.host, self.port)))
        self.assertRaises(ConnectionFailure, Connection,
                          "%s:123456789" % self.host, self.port)

    def test_repr(self):
        self.assertEqual(repr(Connection(self.host, self.port)),
                         "Connection('%s', %s)" % (self.host, self.port))

    def test_getters(self):
        self.assertEqual(Connection(self.host, self.port).host, self.host)
        self.assertEqual(Connection(self.host, self.port).port, self.port)
        self.assertEqual(set([(self.host, self.port)]), Connection(self.host, self.port).nodes)

    def test_get_db(self):
        connection = Connection(self.host, self.port)

        def make_db(base, name):
            return base[name]

        self.assertRaises(InvalidName, make_db, connection, "")
        self.assertRaises(InvalidName, make_db, connection, "te$t")
        self.assertRaises(InvalidName, make_db, connection, "te.t")
        self.assertRaises(InvalidName, make_db, connection, "te\\t")
        self.assertRaises(InvalidName, make_db, connection, "te/t")
        self.assertRaises(InvalidName, make_db, connection, "te st")

        self.assert_(isinstance(connection.test, Database))
        self.assertEqual(connection.test, connection["test"])
        self.assertEqual(connection.test, Database(connection, "test"))
        

class TestConnectionAsync(AsyncTestCase):

    def test_database_names(self):
        connection = Connection(io_loop = self.io_loop)
        
        def callback2(dbs):
            self.assert_("pymongo_test" in dbs)
            self.stop()
            
            
        def callback(resp):       
            connection.database_names(callback2)   
                        
        connection.pymongo_test.test.save({"dummy": u"object"})

        
        self.wait()
        


if __name__ == "__main__":
    unittest.main()
