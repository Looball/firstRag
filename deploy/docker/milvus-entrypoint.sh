#!/bin/sh
# Render the FirstRAG Milvus override from the runtime token, then start.

set -eu

token="${MILVUS_TOKEN:-}"
case "${token}" in
  root:*) root_password="${token#root:}" ;;
  *)
    echo "MILVUS_TOKEN must use the root:<password> bootstrap format." >&2
    exit 2
    ;;
esac

case "${root_password}" in
  ""|*[!A-Za-z0-9._@%+=,-]*)
    echo "MILVUS_TOKEN contains unsupported bootstrap password characters." >&2
    exit 2
    ;;
esac

if [ "${#root_password}" -lt 12 ] || [ "${#root_password}" -gt 72 ]; then
  echo "Milvus root password must contain 12-72 characters." >&2
  exit 2
fi

umask 077
mkdir -p /milvus/configs
printf '%s\n' \
  'etcd:' \
  '  rootPath: firstrag' \
  'minio:' \
  '  bucketName: firstrag' \
  '  rootPath: firstrag' \
  'mq:' \
  '  type: woodpecker' \
  'common:' \
  '  security:' \
  '    authorizationEnabled: true' \
  "    defaultRootPassword: \"${root_password}\"" \
  > /milvus/configs/user.yaml

exec milvus run standalone
