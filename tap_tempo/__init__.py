import json
import os

import singer
from singer import utils
from singer.catalog import Catalog, CatalogEntry, Schema

from . import streams as streams_
from .http_client import Client, Paginator
from .context import Context


REQUIRED_CONFIG_KEYS = ["start_date",
                        "user_agent",
                        "access_token",
                        ]


def get_abs_path(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)


def discover():
    c = Catalog([])
    for stream in streams_.ALL_STREAMS:
        schema = Schema.from_dict(load_schema(stream.tap_stream_id))

        c.streams.append(CatalogEntry(
            stream=stream.tap_stream_id,
            tap_stream_id=stream.tap_stream_id,
            schema=schema,)
        )
    return c


def load_schema(tap_stream_id):
    path = "schemas/{}.json".format(tap_stream_id)
    schema = utils.load_json(get_abs_path(path))
    return schema


def output_schema(stream):
    schema = load_schema(stream.tap_stream_id)
    singer.write_schema(stream.tap_stream_id, schema, stream.pk_fields)


def sync():
    # two loops through streams are necessary so that the schema is output
    # BEFORE syncing any streams. Otherwise, the first stream might generate
    # data for the second stream, but the second stream hasn't output its
    # schema yet
    for stream in streams_.ALL_STREAMS:
        output_schema(stream)

    for stream in streams_.ALL_STREAMS:
        stream.sync()


if __name__ == "__main__":
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)
    catalog = discover()
    Context.config = args.config
    Context.catalog = catalog
    Context.state = args.state
    Context.client = Client(Context.config)
    sync()
    # print(json.dumps(page['results'][0], indent=2))
