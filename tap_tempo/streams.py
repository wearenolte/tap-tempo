import json

import singer
from singer import metrics, utils, metadata, Transformer
from .context import Context


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
        for rec in page['results']:
            with Transformer() as transformer:
                rec = transformer.transform(rec, stream.schema.to_dict())
            singer.write_record(self.tap_stream_id, rec, time_extracted=extraction_time)
        with metrics.record_counter(self.tap_stream_id) as counter:
            counter.increment(len(page))


ACCOUNTS = Stream('accounts', ['id'], path='accounts/')

ALL_STREAMS = [
    ACCOUNTS,
]
