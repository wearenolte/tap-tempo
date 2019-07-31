#!/usr/bin/env bash

/home/nolte/.virtualenvs/tap-tempo/bin/python -m tap-tempo.tap_tempo.__init__ -c tap-tempo/tap_config.json -s tap-tempo/test_state.json | /home/nolte/.virtualenvs/target-stitch/bin/python -m target-stitch.target_stitch.__init__ -n  >> tap-tempo/state.json

tail -1 tap-tempo/state.json > tap-tempo/state.json.tmp && mv tap-tempo/state.json.tmp tap-tempo/state.json