# Copyright 2011 GovData Project.
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

"""Cursor class to iterate over Mongo query results."""

import functools

from bson.code import Code
from bson.son import SON
from apymongo import (helpers,
                     message)
from apymongo.errors import (InvalidOperation,
                            AutoReconnect)

_QUERY_OPTIONS = {
    "tailable_cursor": 2,
    "slave_okay": 4,
    "oplog_replay": 8,
    "no_timeout": 16}


# TODO might be cool to be able to do find().include("foo") or
# find().exclude(["bar", "baz"]) or find().slice("a", 1, 2) as an
# alternative to the fields specifier.
class Cursor(object):
    """A cursor / iterator over Mongo query results.
    
        :Parameters:
          - `collection`: the collection which the cursor is reading.
          - `spec` (optional): the query to read through (unspecified means the whole
          database)
          - `callback`: the callback to call when any reading 
          (kicked off via, e.g. the loop method) is done.
          - `processor`:  online processor callable to be called on each record
          during the process of reading. 
          
          All other parameters are as in PyMongo.
    """

    def __init__(self, collection, 
                 callback = None, 
                 processor = None, 
                 spec=None, 
                 fields=None, 
                 skip=0, 
                 limit=0,
                 timeout=True, 
                 snapshot=False, 
                 tailable=False, 
                 sort=None,
                 max_scan=None, 
                 as_class=None,
                 store = True,
                 _must_use_master=False, 
                 _is_command=False,
                 **kwargs):
        """Create a new cursor.

        Should not be called directly by application developers - see
        :meth:`~pymongo.collection.Collection.find` instead.

        .. mongodoc:: cursors
        """
        self.__id = None

        self.__error = None

        if spec is None:
            spec = {}

        if not isinstance(spec, dict):
            raise TypeError("spec must be an instance of dict")
        if not isinstance(skip, int):
            raise TypeError("skip must be an instance of int")
        if not isinstance(limit, int):
            raise TypeError("limit must be an instance of int")
        if not isinstance(timeout, bool):
            raise TypeError("timeout must be an instance of bool")
        if not isinstance(snapshot, bool):
            raise TypeError("snapshot must be an instance of bool")
        if not isinstance(tailable, bool):
            raise TypeError("tailable must be an instance of bool")

        if fields is not None:
            if not fields:
                fields = {"_id": 1}
            if not isinstance(fields, dict):
                fields = helpers._fields_list_to_dict(fields)

        if as_class is None:
            as_class = collection.database.connection.document_class

        self.__collection = collection
        self.__callback = callback
        self.__processor = processor
        self.__spec = spec
        self.__fields = fields
        self.__skip = skip
        self.__limit = limit
        self.__batch_size = 0
        self.__store = store

        self.__empty = False

        self.__timeout = timeout
        self.__tailable = tailable
        self.__snapshot = snapshot
        self.__ordering = sort and helpers._index_document(sort) or None
        self.__max_scan = max_scan
        self.__explain = False
        self.__hint = None
        self.__as_class = as_class
        self.__tz_aware = collection.database.connection.tz_aware
        self.__must_use_master = _must_use_master
        self.__is_command = _is_command

        self.__data = []
        self.__datastore = []
        self.__connection_id = None
        self.__retrieved = 0
        self.__killed = False

        # this is for passing network_timeout through if it's specified
        # need to use kwargs as None is a legit value for network_timeout
        self.__kwargs = kwargs

    @property
    def collection(self):
        """The :class:`~pymongo.collection.Collection` that this
        :class:`Cursor` is iterating.

        .. versionadded:: 1.1
        """
        return self.__collection

    def __del__(self):
        if self.__id and not self.__killed:
            self.__die()

    def rewind(self):
        """Rewind this cursor to it's unevaluated state.

        Reset this cursor if it has been partially or completely evaluated.
        Any options that are present on the cursor will remain in effect.
        Future iterating performed on this cursor will cause new queries to
        be sent to the server, even if the resultant data has already been
        retrieved by this cursor.
        """
        self.__data = []
        self.__id = None
        self.__connection_id = None
        self.__retrieved = 0
        self.__killed = False

        return self

    def clone(self):
        """Get a clone of this cursor.

        Returns a new Cursor instance with options matching those that have
        been set on the current instance. The clone will be completely
        unevaluated, even if the current instance has been partially or
        completely evaluated.
        """
        copy = Cursor(self.__collection, self.__spec, self.__fields,
                      self.__skip, self.__limit, self.__timeout,
                      self.__tailable, self.__snapshot)
        copy.__ordering = self.__ordering
        copy.__explain = self.__explain
        copy.__hint = self.__hint
        copy.__batch_size = self.__batch_size
        return copy

    def __die(self):
        """Closes this cursor.
        """
        if self.__id and not self.__killed:
            connection = self.__collection.database.connection
            if self.__connection_id is not None:
                connection.close_cursor(self.__id, self.__connection_id)
            else:
                connection.close_cursor(self.__id)
        self.__killed = True

    def __query_spec(self):
        """Get the spec to use for a query.
        """
        spec = self.__spec
        if not self.__is_command and "$query" not in self.__spec:
            spec = SON({"$query": self.__spec})
        if self.__ordering:
            spec["$orderby"] = self.__ordering
        if self.__explain:
            spec["$explain"] = True
        if self.__hint:
            spec["$hint"] = self.__hint
        if self.__snapshot:
            spec["$snapshot"] = True
        if self.__max_scan:
            spec["$maxScan"] = self.__max_scan
        return spec

    def __query_options(self):
        """Get the query options string to use for this query.
        """
        options = 0
        if self.__tailable:
            options |= _QUERY_OPTIONS["tailable_cursor"]
        if self.__collection.database.connection.slave_okay:
            options |= _QUERY_OPTIONS["slave_okay"]
        if not self.__timeout:
            options |= _QUERY_OPTIONS["no_timeout"]
        return options

    def __check_okay_to_chain(self):
        """Check if it is okay to chain more options onto this cursor.
        """
        if self.__retrieved or self.__id is not None:
            raise InvalidOperation("cannot set options after executing query")

    def limit(self, limit):
        """Limits the number of results to be returned by this cursor.

        Raises TypeError if limit is not an instance of int. Raises
        InvalidOperation if this cursor has already been used. The
        last `limit` applied to this cursor takes precedence. A limit
        of ``0`` is equivalent to no limit.

        :Parameters:
          - `limit`: the number of results to return

        .. mongodoc:: limit
        """
        if not isinstance(limit, int):
            raise TypeError("limit must be an int")
        self.__check_okay_to_chain()

        self.__empty = False
        self.__limit = limit
        return self

    def batch_size(self, batch_size):
        """Set the size for batches of results returned by this cursor.

        Raises :class:`TypeError` if `batch_size` is not an instance
        of :class:`int`. Raises :class:`ValueError` if `batch_size` is
        less than ``0``. Raises
        :class:`~pymongo.errors.InvalidOperation` if this
        :class:`Cursor` has already been used. The last `batch_size`
        applied to this cursor takes precedence.

        :Parameters:
          - `batch_size`: The size of each batch of results requested.

        .. versionadded:: 1.9
        """
        if not isinstance(batch_size, int):
            raise TypeError("batch_size must be an int")
        if batch_size < 0:
            raise ValueError("batch_size must be >= 0")
        self.__check_okay_to_chain()

        self.__batch_size = batch_size == 1 and 2 or batch_size
        return self

    def skip(self, skip):
        """Skips the first `skip` results of this cursor.

        Raises TypeError if skip is not an instance of int. Raises
        InvalidOperation if this cursor has already been used. The last `skip`
        applied to this cursor takes precedence.

        :Parameters:
          - `skip`: the number of results to skip
        """
        if not isinstance(skip, (int, long)):
            raise TypeError("skip must be an int")
        self.__check_okay_to_chain()

        self.__skip = skip
        return self

    def max_scan(self, max_scan):
        """Limit the number of documents to scan when performing the query.

        Raises :class:`~pymongo.errors.InvalidOperation` if this
        cursor has already been used. Only the last :meth:`max_scan`
        applied to this cursor has any effect.

        :Parameters:
          - `max_scan`: the maximum number of documents to scan

        .. note:: Requires server version **>= 1.5.1**

        .. versionadded:: 1.7
        """
        self.__check_okay_to_chain()
        self.__max_scan = max_scan
        return self

    def sort(self, key_or_list, direction=None):
        """Sorts this cursor's results.

        Takes either a single key and a direction, or a list of (key,
        direction) pairs. The key(s) must be an instance of ``(str,
        unicode)``, and the direction(s) must be one of
        (:data:`~apymongo.ASCENDING`,
        :data:`~apymongo.DESCENDING`). Raises
        :class:`~apymongo.errors.InvalidOperation` if this cursor has
        already been used. Only the last :meth:`sort` applied to this
        cursor has any effect.

        :Parameters:
          - `key_or_list`: a single key or a list of (key, direction)
            pairs specifying the keys to sort on
          - `direction` (optional): only used if `key_or_list` is a single
            key, if not given :data:`~apymongo.ASCENDING` is assumed
        """
        self.__check_okay_to_chain()
        keys = helpers._index_list(key_or_list, direction)
        self.__ordering = helpers._index_document(keys)
        return self

    def explain(self):
        """Sends explain plan records for this cursor to the callback.
           NB:  Since this is a method that in PyMongo used a "next" call, 
           and since all "next" calls are replaced with "loop" in APyMongo,
           the API for this method diffes between PyMongo and APyMongo. 
           In particular, instead of returning one "explain plan record"
           like PyMongo, the APyMongo explain method returns the list of all 
           explain plan records for the cursor. 

        .. mongodoc:: explain
        """

        self.__explain = True
    
        # always use a hard limit for explains
        if self.__limit:
            self.__limit = -abs(self.__limit)
            
        self.loop()

    def hint(self, index):
        """Adds a 'hint', telling Mongo the proper index to use for the query.

        Judicious use of hints can greatly improve query
        performance. When doing a query on multiple fields (at least
        one of which is indexed) pass the indexed field as a hint to
        the query. Hinting will not do anything if the corresponding
        index does not exist. Raises
        :class:`~pymongo.errors.InvalidOperation` if this cursor has
        already been used.

        `index` should be an index as passed to
        :meth:`~apymongo.collection.Collection.create_index`
        (e.g. ``[('field', ASCENDING)]``). If `index`
        is ``None`` any existing hints for this query are cleared. The
        last hint applied to this cursor takes precedence over all
        others.

        :Parameters:
          - `index`: index to hint on (as an index specifier)
        """
        self.__check_okay_to_chain()
        if index is None:
            self.__hint = None
            return self

        self.__hint = helpers._index_document(index)
        return self

    def where(self, code):
        """Adds a $where clause to this query.

        The `code` argument must be an instance of :class:`basestring`
        or :class:`~bson.code.Code` containing a JavaScript
        expression. This expression will be evaluated for each
        document scanned. Only those documents for which the
        expression evaluates to *true* will be returned as
        results. The keyword *this* refers to the object currently
        being scanned.

        Raises :class:`TypeError` if `code` is not an instance of
        :class:`basestring`. Raises
        :class:`~pymongo.errors.InvalidOperation` if this
        :class:`Cursor` has already been used. Only the last call to
        :meth:`where` applied to a :class:`Cursor` has any effect.

        :Parameters:
          - `code`: JavaScript expression to use as a filter
        """
        self.__check_okay_to_chain()
        if not isinstance(code, Code):
            code = Code(code)

        self.__spec["$where"] = code
        return self

 
    @property
    def alive(self):
        """Does this cursor have the potential to return more data?

        This is mostly useful with `tailable cursors
        <http://www.mongodb.org/display/DOCS/Tailable+Cursors>`_
        since they will stop iterating even though they *may* return more
        results in the future.

        .. versionadded:: 1.5
        """
        return bool(len(self.__data) or (not self.__killed))
               
    def count(self, callback = None, with_limit_and_skip=False):
        """Get the size of the results set for this query.

        Passes the callback the number of documents in the results set for this query. Does
        not take :meth:`limit` and :meth:`skip` into account by default - set
        `with_limit_and_skip` to ``True`` if that is the desired behavior.
        Passes :class:`~apymongo.errors.OperationFailure` on a database error.
        
        Raises assert error if callback is not defined.

        :Parameters:
          - `with_limit_and_skip` (optional): take any :meth:`limit` or
            :meth:`skip` that has been applied to this cursor into account when
            getting the count

        .. note:: The `with_limit_and_skip` parameter requires server
           version **>= 1.1.4-**

        """
        command = {"query": self.__spec, "fields": self.__fields}
        
        if callback is None:
            assert self.__callback is not None, "callback must not be none"
            callback = self.__callback
            

        if with_limit_and_skip:
            if self.__limit:
                command["limit"] = self.__limit
            if self.__skip:
                command["skip"] = self.__skip


        def mod_callback(r):
            if r.get("errmsg", "") == "ns missing":
                callback(0)
            else:
                callback( int(r["n"]) )
            
        
        self.__collection.database.command("count", callback = mod_callback, value = self.__collection.name,
                                               allowable_errors=["ns missing"],
                                               **command)


    def distinct(self, key,callback=None):
        """Get a list of distinct values for `key` among all documents
        in the result set of this query. Passes results to callback

        Raises :class:`TypeError` if `key` is not an instance of
        :class:`basestring`.  Raises assert error if callback is not defined.

        :Parameters:
          - `key`: name of key for which we want to get the distinct values

        .. note:: Requires server version **>= 1.1.3+**

        .. seealso:: :meth:`pymongo.collection.Collection.distinct`

        """
        if not isinstance(key, basestring):
            raise TypeError("key must be an instance of basestring")

        options = {"key": key}
        if self.__spec:
            options["query"] = self.__spec

        if callback is None:
            assert self.__callback is not None, "callback must not be none"
            callback = self.__callback
            
        def mod_callback(resp):
            callback(resp["values"])
            
        self.__collection.database.command("distinct", callback = mod_callback,
                                                  value = self.__collection.name,
                                                  **options)



    def loop(self):
        """
           Replacement of "next" method in the asynchronous context. 
           Basically, one you've defined an apymongo cursor, 
           call the next method to "set it off" and have all the data
           written to the stream.
        
        """
        
        if self.__error:
            self.__callback(self.__error)
            
        else:
            if len(self.__data):
                
                collection = self.__collection
                db = collection.database
                processor = self.__processor
                
                for r in self.__data:
    
                    r = db._fix_outgoing(r, collection)
                   
                    if processor:
                        r = processor(r,collection)
                        
                    if self.__store and r:
                        self.__datastore.append(r)
                        
                
                self.__data = []
                    
                    
            if not self.__killed:
                self._refresh()
                
            else:
                
                self.__callback(self.__datastore)
        
        

    def _refresh(self):
        """Refreshes the cursor with more data from Mongo.

        """

        callback = self.loop
        
        
        if self.__id is None: 
            self.__send_message(
                message.query(self.__query_options(),
                              self.__collection.full_name,
                              self.__skip, self.__limit,
                              self.__query_spec(), self.__fields),callback)

        elif self.__id:  # Get More
            if self.__limit:
                limit = self.__limit - self.__retrieved
                if self.__batch_size:
                    limit = min(limit, self.__batch_size)
            else:
                limit = self.__batch_size

            self.__send_message(
                message.get_more(self.__collection.full_name,
                                 limit, self.__id),callback)



    def __send_message(self, message,callback):
        """Send a query or getmore message and handles the response.
        """
        db = self.__collection.database

        def mod_callback(response):
            
            if isinstance(response,Exception):
                self.__error = response
                      
            else:
                if isinstance(response, tuple):
                    (connection_id, response) = response
                else:
                    connection_id = None
        
                self.__connection_id = connection_id
        
                try:
                    response = helpers._unpack_response(response, self.__id,
                                                        self.__as_class,
                                                        self.__tz_aware)
                except AutoReconnect:
                    db.connection.disconnect()
                    raise
                    
                self.__id = response["cursor_id"]
                 
                # starting from doesn't get set on getmore's for tailable cursors
                if not self.__tailable:                    
                    assert response["starting_from"] == self.__retrieved
        
                self.__retrieved += response["number_returned"]
                self.__data = response["data"]
        
                die_now = (self.__id == 0) or (len(self.__data) == 0) or (self.__limit and self.__id and self.__limit <= self.__retrieved)
        
                if die_now:
                    self.__die()
                                
                
            callback()
    

        db.connection._send_message_with_response(message,mod_callback)




