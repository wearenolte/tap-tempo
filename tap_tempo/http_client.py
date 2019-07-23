from datetime import datetime, timedelta
import time
import json
import requests
from requests import HTTPError

from singer import metrics
import singer
import backoff


class RateLimitException(Exception):
    pass


LOGGER = singer.get_logger()
# > 10ms can help avoid performance issues
TIME_BETWEEN_REQUESTS = timedelta(microseconds=10e3)


def should_retry_httperror(exception):
    """ Retry 500-range errors. """
    return 500 <= exception.response.status_code < 600


class Client:
    def __init__(self, config):
        self.session = requests.Session()
        self.next_request_at = datetime.now()
        self.login_timer = None
        self.user_agent = config.get("user_agent")
        self.access_token = config.get('access_token')
        self.refresh_token = config.get('refresh_token')
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')
        self.redirect_uri = config.get('redirect_uri')
        self.config_path = config.get('config_path')

    def _headers(self, headers):
        headers = headers.copy()
        if self.user_agent:
            headers["User-Agent"] = self.user_agent

        headers['Accept'] = 'application/json'
        headers['Authorization'] = 'Bearer {}'.format(self.access_token)
        return headers

    def send(self, method, path, headers=None, **kwargs):
        if headers is None:
            headers = {}
        request = requests.Request(method,
                                   path,
                                   headers=self._headers(headers),
                                   **kwargs
                                   )
        return self.session.send(request.prepare())

    @backoff.on_exception(backoff.expo,
                          HTTPError,
                          jitter=None,
                          max_tries=6,
                          giveup=lambda e: not should_retry_httperror(e))
    @backoff.on_exception(backoff.constant,
                          RateLimitException,
                          max_tries=10,
                          interval=60)
    def request(self, tap_stream_id, *args, **kwargs):
        wait = (self.next_request_at - datetime.now()).total_seconds()
        if wait > 0:
            time.sleep(wait)
        with metrics.http_request_timer(tap_stream_id) as timer:
            response = self.send(*args, **kwargs)
            self.next_request_at = datetime.now() + TIME_BETWEEN_REQUESTS
            timer.tags[metrics.Tag.http_status_code] = response.status_code
        if response.status_code == 429:
            raise RateLimitException()
        response.raise_for_status()
        return response.json()


class Paginator:
    def __init__(self, client, next_page_url):
        self.client = client
        self.next_page_url = next_page_url

    def pages(self, *args, **kwargs):
        """Returns a generator which yields pages of data using "next" key in metadata.
        :param args: Passed to Client.request
        :param kwargs: Passed to Client.request
        """
        params = kwargs.pop("params", {}).copy()
        while self.next_page_url is not None:
            page = self.client.request(*args, path=self.next_page_url, params=params, **kwargs)
            self.next_page_url = page['metadata'].get('next', None)
            if page:
                yield page['results']
