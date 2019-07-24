import json
from datetime import date

import singer
from singer import metrics, utils, Transformer
from .context import Context
from .http_client import Paginator


BASE_URL = 'https://api.tempo.io/core/3/{}'


class Stream:
    """Information about and functions for syncing streams for the Tempo API.
    Important class properties:
    :var tap_stream_id:
    :var pk_fields: A list of primary key fields
    directly, but instead has its data generated via a separate stream."""

    def __init__(self, tap_stream_id, pk_fields,page_limit=None, path=None):
        self.tap_stream_id = tap_stream_id
        self.pk_fields = pk_fields
        # Only used to skip streams in the main sync function
        self.path = BASE_URL.format(path)
        self.page_limit = page_limit

    def __repr__(self):
        return "<Stream(" + self.tap_stream_id + ")>"

    def sync(self):
        pager = Paginator(client=Context.client, next_page_url=self.path)
        for page in pager.pages(tap_stream_id=self.tap_stream_id, method="GET"):
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


class StatefulStream(Stream):

    def sync(self):
        updated_bookmark = [self.tap_stream_id, "updated"]
        last_updated = Context.get_start_date_bookmark(updated_bookmark)
        params = {
            "from": Context.config["start_date"],
            "to": str(date.today()),
            "updatedFrom": last_updated,
        }
        if self.page_limit:
            params['limit'] = self.page_limit
        pager = Paginator(client=Context.client, next_page_url=self.path)
        for page in pager.pages(tap_stream_id=self.tap_stream_id, method="GET", params=params):
            self.write_page(page)

        Context.set_bookmark(updated_bookmark, str(date.today()))
        singer.write_state(Context.state)


ACCOUNTS = Stream("accounts", ["id"], path="accounts/")
PLANS = StatefulStream("plans", ["id"], path="plans/", page_limit=500)
WORKLOGS = StatefulStream("worklogs", ["tempoWorklogId"], path="worklogs/", page_limit=500)

ALL_STREAMS = [
    ACCOUNTS,
    PLANS,
    #WORKLOGS,
]
