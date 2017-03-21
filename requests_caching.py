# Standard Library Imports
from functools import partial
import io

# Requests Imports
import requests
from requests.adapters import HTTPAdapter
# noinspection PyUnresolvedReferences
from requests.packages.urllib3 import disable_warnings
# noinspection PyUnresolvedReferences
from requests.packages.urllib3.response import HTTPResponse

# Package imports
from urlquick import CacheAdapter as BaseCacheAdapter

# Disable requests ssl warnings
disable_warnings()


class Session(requests.Session):
    def __init__(self):
        super(Session, self).__init__()
        self.mount('https://', CacheAdapter())
        self.mount('http://', CacheAdapter())


class CacheAdapter(HTTPAdapter, BaseCacheAdapter):
    @staticmethod
    def callback(response):
        # Fetch the body of the response
        if response.chunked:
            body = b"".join([chunk for chunk in response.stream(decode_content=False)])
        else:
            body = response.read(decode_content=False)

        response.release_conn()
        return response.headers, body, response.status, response.reason, response.version, response.strict

    @staticmethod
    def prepare_response(response):
        """ Prepare the cached response so that requests can handle it """
        body = io.BytesIO(response.pop("body"))
        return HTTPResponse(body=body, preload_content=False, **response)

    def send(self, request, **kwargs):
        """
        Use the request information to check if it exists in the cache
        and return cached response if so. Else forward on the request
        """
        # Check if reuest is cached and also fresh
        cache_resp = self.cache_check(request.method, request.url, request.body, request.headers)
        if cache_resp:
            response = self.prepare_response(cache_resp)
            return super(CacheAdapter, self).build_response(request, response)
        else:
            # Forward the request to the server
            return super(CacheAdapter, self).send(request, verify=False, **kwargs)

    def build_response(self, request, response):
        """ Build a requests response object """
        callback = partial(self.callback, response)
        cache_resp = self.handle_response(request.method, response.status, callback)
        if cache_resp:
            response = self.prepare_response(cache_resp)

        # Send the urllib3 response to requests, for requests to build it's response
        return super(CacheAdapter, self).build_response(request, response)
