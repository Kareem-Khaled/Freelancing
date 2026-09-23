#!/usr/bin/env bash
#
# Run the offline test suite. No model server or network required.
#
#   ./test.sh          run everything
#   ./test.sh -v       verbose, one line per test

set -euo pipefail
cd "$(dirname "$0")"

exec python3 -m unittest discover -s tests "$@"
