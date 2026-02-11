#!/usr/bin/env bash
set -e

VERSION=${1:-1.0.0}
IMAGE=auth-api

echo "Building ${IMAGE}:${VERSION} (no cache)"
docker build --no-cache -t ${IMAGE}:${VERSION} .
