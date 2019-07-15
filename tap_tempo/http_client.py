from datetime import datetime, timedelta
import time
import threading
import re
import json
from requests.exceptions import HTTPError
from requests.auth import HTTPBasicAuth
import requests

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
        self.user_agent = config.get("user_agent")
        self.login_timer = None

        LOGGER.info("Using OAuth based API authentication")
        self.base_url = 'https://api.tempo.io/core/3/{}{}'
        self.cloud_id = config.get('cloud_id')
        self.access_token = config.get('access_token')
        self.refresh_token = config.get('refresh_token')
        self.oauth_client_id = config.get('oauth_client_id')
        self.oauth_client_secret = config.get('oauth_client_secret')
        self.redirect_uri = config.get('redirect_uri')

        # Auth token lasts 60 days.
        # Refreshing token every first day of the month would suffice.
        if datetime.today().day == 1:
            self.refresh_credentials()
            self.test_credentials_are_authorized()

        def send():
            pass

        def request():
            pass

        def refresh_credentials(self):
            body = {
                "grant_type": "refresh_token",
                "client_id": self.oauth_client_id,
                "client_secret": self.oauth_client_secret,
                "refresh_token": self.refresh_token,
                "redirect_uri": self.redirect_uri,
            }
            try:
                resp = self.session.post("https://api.tempo.io/oauth/token", data=body)
                resp.raise_for_status()
                self.access_token = resp.json()['access_token']
                # Update config file
                with open('config.json', 'r+') as f:
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