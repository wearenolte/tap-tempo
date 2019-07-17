from datetime import datetime, timedelta
import time
import threading
import re
import json
from requests.exceptions import HTTPError
from requests.auth import HTTPBasicAuth
import requests
from singer import utils

from singer import metrics
import singer
import backoff


class RateLimitException(Exception):
    pass


LOGGER = singer.get_logger()
# > 10ms can help avoid performance issues
TIME_BETWEEN_REQUESTS = timedelta(microseconds=10e3)


class Client:
    def __init__(self, config):
        self.session = requests.Session()
        self.next_request_at = datetime.now()
        self.login_timer = None
        self.base_url = 'https://api.tempo.io/core/3/{}'
        self.user_agent = config.get("user_agent")
        self.access_token = config.get('access_token')
        self.refresh_token = config.get('refresh_token')
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')
        self.redirect_uri = config.get('redirect_uri')
        self.config_path = config.get('config_path')

        # Auth token lasts 60 days.
        # Refreshing token every first day of the month would suffice.
        if datetime.today().day == 1:
            self.refresh_credentials()
            self.test_credentials_are_authorized()

    def _headers(self, headers):
        headers = headers.copy()
        if self.user_agent:
            headers["User-Agent"] = self.user_agent

        headers['Accept'] = 'application/json'
        headers['Authorization'] = 'Bearer {}'.format(self.access_token)
        return headers

    def send(self, method, path, headers={}, **kwargs):
        request = requests.Request(method,
                                   path,
                                   headers=self._headers(headers),
                                   **kwargs
                                   )
        return self.session.send(request.prepare())

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

    def refresh_credentials(self):
        # Refresh access token and write new token on config file
        body = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "redirect_uri": self.redirect_uri,
        }
        try:
            resp = self.session.post("https://api.tempo.io/oauth/token", data=body)
            resp.raise_for_status()
            self.access_token = resp.json()['access_token']
            # Update config file
            with open(self.config_path, 'r+') as f:
                data = json.load(f)
                data['access_token'] = self.access_token
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        except Exception as e:
            error_message = str(e)
            if resp:
                error_message = error_message + ", Response from Tempo: {}".format(resp.text)
            raise Exception(error_message) from e