#!/bin/sh
set -eu

export AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-/tmp/azure-config}"
mkdir -p "$AZURE_CONFIG_DIR"
if [ -d /azure-cli-config ]; then
  cp -R /azure-cli-config/. "$AZURE_CONFIG_DIR"/
fi

exec "$@"
