#!/bin/bash
# Configure from staged files so the source and install locations differ.
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")" && pwd)
stage=$("$root/stage_install.sh")
trap 'rm -rf "$stage"' EXIT
"$stage/install.sh" "$@"
