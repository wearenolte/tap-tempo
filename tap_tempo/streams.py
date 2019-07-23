import json

import singer
from singer import metrics, utils, Transformer
from .context import Context
from .http_client import Paginator


BASE_URL = 'https://api.tempo.io/core/3/{}'


class Stream:
    """Information about and functions for syncing streams for the Jira API.
    Important class properties:
    :var tap_stream_id:
    :var pk_fields: A list of primary key fields
    :var indirect_stream: If True, this indicates the stream cannot be synced
    directly, but instead has its data generated via a separate stream."""

    def __init__(self, tap_stream_id, pk_fields, indirect_stream=False, path=None):
        self.tap_stream_id = tap_stream_id
        self.pk_fields = pk_fields
        # Only used to skip streams in the main sync function
        self.indirect_stream = indirect_stream
        self.path = BASE_URL.format(path)

    def __repr__(self):
        return "<Stream(" + self.tap_stream_id + ")>"

    def sync(self):
        page = Context.client.request(tap_stream_id=self.tap_stream_id, method="GET", path=self.path)
        self.write_page(page)

    def write_page(self, page):
        stream = Context.get_catalog_entry(self.tap_stream_id)
        extraction_time = singer.utils.now()
        for rec in page:
            with Transformer() as transformer:
                rec = transformer.transform(rec, stream.schema.to_dict())
            singer.write_record(self.tap_stream_id, rec, time_extracted=extraction_time)
        with metrics.record_counter(self.tap_stream_id) as counter:
            counter.increment(len(page))


class Accounts(Stream):
    """
    Keeps state through last added id
    """

    def sync(self):
        updated_bookmark = [self.tap_stream_id, "updated"]
        last_updated_id = Context.get_id_bookmark(updated_bookmark)
        print(last_updated_id)
        idx = []
        pager = Paginator(client=Context.client, next_page_url=self.path)
        for page in pager.pages(tap_stream_id=self.tap_stream_id, method="GET"):
            page = [rec for rec in page if rec["id"] > last_updated_id]
            idx += [rec["id"] for rec in page]
            self.write_page(page)

        if len(idx) > 0:
            last_updated_id = max(idx)
        Context.set_bookmark(updated_bookmark, last_updated_id)
        singer.write_state(Context.state)


class Plans(Stream):

    def sync(self):
        updated_bookmark = [self.tap_stream_id, "updated"]
        last_updated = Context.get_start_date_bookmark(updated_bookmark)
        print(last_updated.date())
        # pager = Paginator(client=Context.client, next_page_url=self.path)
        # params = {
        #     'from': '2019-06-01',
        #     'to': '2019-07-22'
        # }
        # for page in pager.pages(tap_stream_id=self.tap_stream_id, params=params):
        #     print(len(page['results']))


ACCOUNTS = Accounts('accounts', ['id'], path='accounts/')
PLANS = Plans('plans', ['id'], path='plans/')

ALL_STREAMS = [
    ACCOUNTS,
    #PLANS,
]
