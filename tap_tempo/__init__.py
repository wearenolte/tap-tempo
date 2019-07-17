from singer import utils

from .streams import Stream
from .http_client import Client
from .context import Context


REQUIRED_CONFIG_KEYS = ["start_date",
                        "user_agent",
                        "access_token",
                        ]


if __name__ == "__main__":
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)
    Context.config = args.config
    Context.client = Client(Context.config)
    account_stream = Stream('accounts', ['id'], path='accounts/')
    account_stream.sync()