#!/usr/bin/env sh
set -eu

BROKERS="${KAFKA_BROKERS:-localhost:9092}"
PARTITIONS="${KAFKA_PARTITIONS:-6}"
REPLICATION="${KAFKA_REPLICATION_FACTOR:-1}"

for topic in \
  telemetry.raw \
  telemetry.normalized \
  topology.events \
  incident.signals \
  memory.edges \
  memory.patterns \
  remediation.events \
  feedback.events
do
  kafka-topics --bootstrap-server "$BROKERS" \
    --create \
    --if-not-exists \
    --topic "$topic" \
    --partitions "$PARTITIONS" \
    --replication-factor "$REPLICATION"
done
