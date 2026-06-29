
import os
import json
import base64
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping
import traceback
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import boto3  # Provided in AWS runtime; optional locally
except Exception:  # ModuleNotFoundError or others
    boto3 = None


# Globals
S3 = None  # Lazy init to allow local dry-run without boto3
RAW_BUCKET_NAME = os.getenv("RAW_BUCKET_NAME", "zoolanding-data-raw")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DRY_RUN = os.getenv("DRY_RUN", "0") in {"1", "true", "TRUE", "yes", "YES"}
TIMESTAMP_MS_THRESHOLD = 10**12
SAFE_ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
BLOG_SENSITIVE_FIELDS = {
    "email",
    "phone",
    "phoneNumber",
    "password",
    "token",
    "accessToken",
    "refreshToken",
    "idToken",
    "authorization",
    "commentBody",
    "message",
    "body",
}
BLOG_SENSITIVE_FIELD_KEYS = {re.sub(r"[^a-z0-9]", "", field.lower()) for field in BLOG_SENSITIVE_FIELDS}
EMAIL_VALUE_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_VALUE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
SECRET_VALUE_RE = re.compile(
    r"(?:bearer\s+[a-z0-9._~+/=-]+|x-amz-signature|x-amz-credential|"
    r"-----BEGIN |AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16})",
    re.I,
)


@dataclass(frozen=True)
class EventTime:
    timestamp_ms: int
    utc: str
    timezone_name: str | None = None
    local: str | None = None
    local_date: str | None = None
    local_hour: str | None = None

    def to_response(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "timestampMs": self.timestamp_ms,
            "utc": self.utc,
        }
        if self.timezone_name and self.local and self.local_date and self.local_hour:
            payload.update(
                {
                    "timezone": self.timezone_name,
                    "local": self.local,
                    "localDate": self.local_date,
                    "localHour": self.local_hour,
                }
            )
        return payload

    def to_s3_metadata(self) -> Dict[str, str]:
        metadata = {
            "timestamp-ms": str(self.timestamp_ms),
            "event-time-utc": self.utc,
        }
        if self.timezone_name and self.local and self.local_date and self.local_hour:
            metadata.update(
                {
                    "event-timezone": self.timezone_name,
                    "event-time-local": self.local,
                    "event-local-date": self.local_date,
                    "event-local-hour": self.local_hour,
                }
            )
        return metadata


def _should_log(level: str) -> bool:
    order = {"DEBUG": 10, "INFO": 20, "ERROR": 40}
    return order.get(level, 20) >= order.get(LOG_LEVEL, 20)


def _log(level: str, message: str, **fields: Any) -> None:
    if not _should_log(level):
        return
    record = {
        "level": level,
        "message": message,
        **fields,
    }
    try:
        print(json.dumps(record, ensure_ascii=False))
    except Exception:
        # Fallback to plain print if non-serializable
        print({"level": level, "message": message, "_text": str(fields)})


def _json_response(status: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(payload, separators=(",", ":")),
    }


def _bad_request(msg: str) -> Dict[str, Any]:
    return _json_response(400, {"ok": False, "error": msg})


def _server_error() -> Dict[str, Any]:
    return _json_response(500, {"ok": False, "error": "Internal error"})


def _get_request_id(context: Any) -> str:
    request_id = None
    try:
        request_id = getattr(context, "aws_request_id", None)
    except Exception:
        request_id = None
    if isinstance(request_id, str) and len(request_id) >= 8:
        # Keep only the suffix so filenames stay short while still carrying
        # a request-scoped uniqueness hint from the Lambda invocation.
        return request_id[-8:]
    # Fallback to a short timestamp-based suffix for local or synthetic invocations.
    return hex(int(datetime.now(tz=timezone.utc).timestamp() * 1000))[-8:]


def _decode_body(event: Dict[str, Any]) -> str:
    body = event.get("body")
    if body is None or body == "":
        raise ValueError("Missing body")
    is_base64_encoded = event.get("isBase64Encoded", False)
    if is_base64_encoded:
        # API Gateway-compatible invokers may deliver the request body as base64.
        if isinstance(body, str):
            return base64.b64decode(body).decode("utf-8")
        raise ValueError("Body is base64Encoded but not a string")
    if isinstance(body, (str, bytes)):
        return body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body
    # Some invokers might already pass dict; accept it by re-serializing
    return json.dumps(body)


def _normalize_timestamp_to_ms(ts: Any) -> int:
    if not isinstance(ts, (int, float)) or not math.isfinite(ts):
        raise ValueError("Missing or invalid timestamp")
    # Accept both epoch seconds and epoch milliseconds so older or simpler
    # clients do not need an exact timestamp unit contract.
    ts_ms = int(ts if ts >= TIMESTAMP_MS_THRESHOLD else ts * 1000)
    return ts_ms


def _derive_date_parts(ts_ms: int) -> tuple[str, str, str]:
    # Use UTC for partition keys to avoid locale- or DST-dependent drift.
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")


def _format_iso(dt: datetime) -> str:
    timespec = "milliseconds" if dt.microsecond else "seconds"
    value = dt.isoformat(timespec=timespec)
    if dt.utcoffset() == timedelta(0):
        return value.replace("+00:00", "Z")
    return value


def _event_time_from_payload(ts_ms: int, payload: Mapping[str, Any]) -> EventTime:
    utc_dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    timezone_name = payload.get("timezone")
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        return EventTime(timestamp_ms=ts_ms, utc=_format_iso(utc_dt))

    timezone_name = timezone_name.strip()
    try:
        local_dt = utc_dt.astimezone(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError:
        return EventTime(timestamp_ms=ts_ms, utc=_format_iso(utc_dt))

    return EventTime(
        timestamp_ms=ts_ms,
        utc=_format_iso(utc_dt),
        timezone_name=timezone_name,
        local=_format_iso(local_dt),
        local_date=local_dt.strftime("%Y-%m-%d"),
        local_hour=local_dt.strftime("%H"),
    )


def _safe_slug(value: Any, field_name: str) -> str:
    slug = str(value or "").strip().lower()
    if len(slug) < 2 or len(slug) > 80 or not all(char in SAFE_ID_CHARS for char in slug):
        raise ValueError(f"Missing or invalid {field_name}")
    return slug


def _is_blog_event(payload: Mapping[str, Any]) -> bool:
    name = str(payload.get("name") or "").strip().lower()
    feature = str(payload.get("feature") or payload.get("contentFeature") or "").strip().lower()
    content_type = str(payload.get("contentType") or "").strip().lower()
    return feature == "blog" or content_type in {"blog", "blogarticle", "blog-article"} or name.startswith("blog_")


def _validate_blog_event(payload: Mapping[str, Any]) -> None:
    if not _is_blog_event(payload):
        return

    _safe_slug(payload.get("contentHubId") or payload.get("hubId"), "contentHubId")
    _safe_slug(payload.get("articleId") or payload.get("slug"), "articleId")
    for field_name in BLOG_SENSITIVE_FIELDS:
        if field_name in payload:
            raise ValueError(f"Blog analytics events must not include '{field_name}'")
    _reject_blog_sensitive_node(payload)


def _reject_blog_sensitive_node(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            key_token = re.sub(r"[^a-z0-9]", "", key_text.lower())
            if key_token in BLOG_SENSITIVE_FIELD_KEYS:
                raise ValueError(f"Blog analytics events must not include '{key_text}'")
            _reject_blog_sensitive_node(child)
        return
    if isinstance(value, list):
        for child in value:
            _reject_blog_sensitive_node(child)
        return
    if isinstance(value, str) and (
        EMAIL_VALUE_RE.search(value) or PHONE_VALUE_RE.search(value) or SECRET_VALUE_RE.search(value)
    ):
        raise ValueError("Blog analytics events must not include private values")


def _get_s3_client():
    global S3
    if S3 is not None:
        return S3
    if DRY_RUN:
        # Local dry-runs should exercise the handler flow without requiring AWS creds.
        _log("DEBUG", "DRY_RUN enabled; skipping S3 client init")
        return None
    if boto3 is None:
        _log("ERROR", "boto3 not available and DRY_RUN is disabled; cannot upload to S3")
        raise RuntimeError("boto3 is not available and DRY_RUN is disabled; cannot upload to S3")
    S3 = boto3.client("s3")
    _log("DEBUG", "Initialized S3 client")
    return S3


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    short_request_id = _get_request_id(context)

    try:
        # 1) Decode body
        body_str = _decode_body(event)
        _log("DEBUG", "Decoded body", requestId=short_request_id, decodedLen=len(body_str))

        # 2) Parse JSON
        try:
            payload = json.loads(body_str)
        except Exception as e:
            _log("ERROR", "Invalid JSON", requestId=short_request_id, error=str(e))
            return _bad_request("Body is not valid JSON")
        if not isinstance(payload, dict):
            _log("ERROR", "Body JSON is not an object", requestId=short_request_id, payloadType=type(payload).__name__)
            return _bad_request("Body JSON must be an object")

        # 3) Validate fields
        app_name = payload.get("appName")
        if not isinstance(app_name, str) or not app_name.strip():
            _log("ERROR", "Invalid appName", requestId=short_request_id)
            return _bad_request("Missing or invalid appName")

        try:
            ts_ms = _normalize_timestamp_to_ms(payload.get("timestamp"))
        except ValueError as e:
            _log("ERROR", str(e), requestId=short_request_id, appName=app_name)
            return _bad_request(str(e))
        try:
            _validate_blog_event(payload)
        except ValueError as e:
            _log("ERROR", str(e), requestId=short_request_id, appName=app_name)
            return _bad_request(str(e))
        _log(
            "DEBUG",
            "Validated payload",
            requestId=short_request_id,
            appName=app_name,
            timestampType=type(payload.get("timestamp")).__name__,
            timestampMs=ts_ms,
            keys=list(payload.keys())[:12],
        )

        # 4) Derive date parts (UTC) and optional viewer-local time fields.
        yyyy, mm, dd = _derive_date_parts(ts_ms)
        event_time = _event_time_from_payload(ts_ms, payload)
        _log(
            "DEBUG",
            "Derived date parts",
            requestId=short_request_id,
            yyyy=yyyy,
            mm=mm,
            dd=dd,
            eventTime=event_time.to_response(),
        )

        # 5) Build S3 key
        # Prefix by app and UTC calendar date so downstream jobs can read by
        # app/day without scanning unrelated raw objects.
        key = f"{app_name}/{yyyy}/{mm}/{dd}/{ts_ms}-{short_request_id}.json"

        # 6) Upload original, unchanged body string
        body_bytes = body_str.encode("utf-8")
        size_bytes = len(body_bytes)
        if DRY_RUN:
            _log(
                "INFO",
                "Dry-run: would upload",
                requestId=short_request_id,
                appName=app_name,
                timestampMs=ts_ms,
                bucket=RAW_BUCKET_NAME,
                key=key,
                size=size_bytes,
                dryRun=True,
                eventTime=event_time.to_response(),
            )
        else:
            try:
                s3 = _get_s3_client()
                # Store the raw JSON exactly as received. Any enrichment or
                # normalization beyond the key naming belongs to later stages.
                s3.put_object(
                    Bucket=RAW_BUCKET_NAME,
                    Key=key,
                    Body=body_bytes,
                    ContentType="application/json",
                    Metadata=event_time.to_s3_metadata(),
                )
                _log(
                    "INFO",
                    "Uploaded analytics payload",
                    requestId=short_request_id,
                    appName=app_name,
                    timestampMs=ts_ms,
                    bucket=RAW_BUCKET_NAME,
                    key=key,
                    size=size_bytes,
                    eventTime=event_time.to_response(),
                )
            except Exception as s3_error:
                _log(
                    "ERROR",
                    "S3 upload failed",
                    requestId=short_request_id,
                    appName=app_name,
                    bucket=RAW_BUCKET_NAME,
                    key=key,
                    error=str(s3_error),
                    stack=traceback.format_exc(),
                )
                # Server error for unexpected S3 failures
                return _server_error()

        # 7) Return success
        body = {
            "ok": True,
            "size": size_bytes,
            "eventTime": event_time.to_response(),
        }
        if DRY_RUN:
            body["dryRun"] = True
        return _json_response(200, body)

    except ValueError as ve:
        # Validation failures map to 400 because the caller can fix the payload.
        _log("ERROR", "Bad request", requestId=short_request_id, error=str(ve))
        return _bad_request(str(ve))
    except Exception as ex:
        # Anything else is treated as an internal failure such as S3 or runtime issues.
        _log("ERROR", "Unhandled error", requestId=short_request_id, error=str(ex), stack=traceback.format_exc())
        return _server_error()
