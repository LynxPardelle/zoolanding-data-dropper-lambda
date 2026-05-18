# ETL Starting Point

This document explains what the Data Dropper Lambda guarantees and how a future ETL pipeline should use the raw analytics objects it writes.

## Purpose

`zoolanding-data-dropper-lambda` is the raw analytics ingestion boundary for Zoolanding.

Its job is intentionally narrow:

- receive browser analytics payloads through `POST /analytics`
- validate only the minimum contract needed to store the event safely
- normalize timestamp units for storage naming and metadata
- write the original request body unchanged to S3
- keep enough object metadata to make downstream discovery easier

It is not an analytics warehouse, aggregation Lambda, dashboard backend, identity service, or ETL processor.

## Raw Storage Contract

Each accepted event is written to S3 with this layout:

```text
s3://<raw-bucket>/<appName>/<YYYY>/<MM>/<DD>/<timestampMs>-<shortRequestId>.json
```

The `YYYY/MM/DD` partition is derived from `timestamp` in UTC. This is the stable partitioning standard for raw storage, even when the payload also contains a viewer timezone.

The object body is the original request body string. The Lambda does not add, remove, rename, or reformat fields inside the JSON body.

## Minimum Payload Fields

The Lambda requires:

- `appName`: non-empty string used as the top-level S3 prefix
- `timestamp`: finite number in epoch seconds or epoch milliseconds

Useful payload fields for ETL include:

- `sessionId`: connects events from the same browser session
- `localId`: connects sessions from the same browser storage identity when available
- `timezone`: IANA timezone from the browser, for example `America/Mexico_City`
- `name`, `category`, `label`, `value`, `meta`: event semantics from the frontend
- `language`, `userAgent`, `platform`, screen fields, and other configured analytics context

Do not assume every event has every optional field. The frontend may send richer context on an early event and smaller payloads later in the same session.

## Time Fields

The Lambda derives and exposes:

- `timestampMs`: normalized event timestamp in milliseconds
- `event-time-utc`: UTC instant as S3 metadata
- `event-timezone`: S3 metadata only when the payload includes a valid IANA timezone
- `event-time-local`: viewer-local timestamp only when `timezone` is valid
- `event-local-date`: viewer-local date only when `timezone` is valid
- `event-local-hour`: viewer-local hour only when `timezone` is valid

If `timezone` is absent or invalid, the raw event is still accepted. The Lambda reports UTC-only time fields because it must not infer the viewer timezone from AWS region, IP address, or incomplete request headers.

## Session Timezone Strategy For ETL

The future ETL should resolve timezone at the session level instead of requiring every event to repeat `timezone`.

Recommended approach:

1. Read raw objects for the target `appName` and UTC date range.
2. Parse each JSON object body and preserve source metadata such as bucket, key, and object timestamp metadata.
3. Normalize each payload timestamp to `timestampMs` using the same seconds-vs-milliseconds rule.
4. Group events by `sessionId` when present.
5. For each session, choose a session timezone from the earliest event in timestamp order that has a valid IANA `timezone`.
6. Apply that session timezone to later events in the same session that do not include `timezone`.
7. If a later event has a different valid timezone, keep both facts: the event timezone and the original session timezone. Do not silently overwrite without recording that timezone changed during the session.
8. If a session has no valid timezone, keep UTC-only derived fields and mark timezone resolution as unknown.

This keeps browser payloads small and avoids changing Zoolandingpage just to repeat the same timezone on every analytics event.

## Suggested ETL Output Columns

The first normalized table can stay close to raw data:

- `app_name`
- `session_id`
- `local_id`
- `event_name`
- `event_category`
- `event_label`
- `event_value`
- `event_timestamp_ms`
- `event_time_utc`
- `event_timezone`
- `session_timezone`
- `event_time_local`
- `event_local_date`
- `event_local_hour`
- `source_bucket`
- `source_key`
- `source_ingested_at`
- `raw_payload`

Keep `raw_payload` or a pointer to the raw S3 object so future transforms can be replayed when the event model changes.

## Ordering And Deduplication

Use `timestampMs` for event ordering within a session. Use the S3 key suffix only as a uniqueness hint from the Lambda request id.

Do not treat S3 object listing order as event order.

If the frontend later adds an idempotency field, ETL can use it for deduplication. Until then, a practical dedupe key can include:

- `appName`
- `sessionId`
- `timestamp`
- `name`
- `category`
- `label`
- `source_key`

Do not drop events solely because they share the same timestamp; browsers can emit several events in the same millisecond.

## Privacy And Security Notes

The raw bucket may contain analytics context controlled by draft configuration. Treat raw objects as sensitive operational data.

ETL should not add sensitive enrichment such as raw IP, precise geolocation, raw cookies, or customer PII unless the configured consent flow and compliance review explicitly approve it.

Timezone is useful for local-hour reporting, but it is not proof of exact physical location.

## Non-Goals

This Lambda does not:

- validate the full event schema
- guarantee every optional analytics field is present
- join events by session
- infer missing timezone
- aggregate page views, CTA clicks, or funnel metrics
- delete, compact, or transform raw objects

Those responsibilities belong in the future ETL or analytics reporting layer.

## First ETL Milestone

The first ETL pass should produce a normalized event table from raw S3 objects with UTC and session-local time fields. It should prove:

- every accepted object can be parsed or quarantined with an error reason
- events can be grouped by `appName` and `sessionId`
- timezone can be resolved per session when at least one event provides it
- UTC partitioning remains the raw storage read strategy
- raw payloads remain replayable
