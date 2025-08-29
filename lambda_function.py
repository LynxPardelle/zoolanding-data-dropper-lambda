
import os
import json
import base64
import math
from datetime import datetime, timezone
from typing import Any, Dict
import traceback

try:
    import boto3  # Provided in AWS runtime; optional locally
except Exception:  # ModuleNotFoundError or others
    boto3 = None


# Globals
S3 = None  # Lazy init to allow local dry-run without boto3
RAW_BUCKET_NAME = os.getenv("RAW_BUCKET_NAME", "zoolanding-data-raw")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DRY_RUN = os.getenv("DRY_RUN", "0") in {"1", "true", "TRUE", "yes", "YES"}


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
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, separators=(",", ":")),
    }


def _bad_request(msg: str) -> Dict[str, Any]:
    return _json_response(400, {"ok": False, "error": msg})


def _server_error() -> Dict[str, Any]:
    return _json_response(500, {"ok": False, "error": "Internal error"})


def _get_request_id(context: Any) -> str:
    reqId = None
    try:
        reqId = getattr(context, "aws_request_id", None)
    except Exception:
        reqId = None
    if isinstance(reqId, str) and len(reqId) >= 8:
        # Per spec, use the LAST 8 characters
        return reqId[-8:]
    # Fallback to a random-ish short id without importing uuid for minimal deps
    # Use current time ticks in ms hex last 8 chars
    return hex(int(datetime.now(tz=timezone.utc).timestamp() * 1000))[-8:]


def _decode_body(event: Dict[str, Any]) -> str:
    body = event.get("body")
    if body is None or body == "":
        raise ValueError("Missing body")
    is_b64 = event.get("isBase64Encoded", False)
    if is_b64:
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
    ts_ms = int(ts if ts >= 10**12 else ts * 1000)
    return ts_ms


def _derive_date_parts(ts_ms: int):
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")


def _get_s3_client():
    global S3
    if S3 is not None:
        return S3
    if DRY_RUN:
        _log("DEBUG", "DRY_RUN enabled; skipping S3 client init")
        return None
    if boto3 is None:
        _log("ERROR", "boto3 not available and DRY_RUN is disabled; cannot upload to S3")
        raise RuntimeError("boto3 is not available and DRY_RUN is disabled; cannot upload to S3")
    S3 = boto3.client("s3")
    try:
        # Try a lightweight call to ensure client is usable (won't fail without creds until used)
        _log("DEBUG", "Initialized S3 client")
    except Exception as e:
        _log("ERROR", "Failed to initialize S3 client", error=str(e))
    return S3


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    short_reqId = _get_request_id(context)

    try:
        # 1) Decode body
        body_str = _decode_body(event)
        _log("DEBUG", "Decoded body", requestId=short_reqId, decodedLen=len(body_str))

        # 2) Parse JSON
        try:
            payload = json.loads(body_str)
        except Exception as e:
            _log("ERROR", "Invalid JSON", requestId=short_reqId, error=str(e))
            return _bad_request("Body is not valid JSON")

        # 3) Validate fields
        app_name = payload.get("appName")
        if not isinstance(app_name, str) or not app_name.strip():
            _log("ERROR", "Invalid appName", requestId=short_reqId)
            return _bad_request("Missing or invalid appName")

        try:
            ts_ms = _normalize_timestamp_to_ms(payload.get("timestamp"))
        except ValueError as e:
            _log("ERROR", str(e), requestId=short_reqId, appName=app_name)
            return _bad_request(str(e))
        _log(
            "DEBUG",
            "Validated payload",
            requestId=short_reqId,
            appName=app_name,
            timestampType=type(payload.get("timestamp")).__name__,
            timestampMs=ts_ms,
            keys=list(payload.keys())[:12],
        )

        # 4) Derive date parts (UTC)
        yyyy, mm, dd = _derive_date_parts(ts_ms)
        _log("DEBUG", "Derived date parts", requestId=short_reqId, yyyy=yyyy, mm=mm, dd=dd)

        # 5) Build S3 key
        key = f"{app_name}/{yyyy}/{mm}/{dd}/{ts_ms}-{short_reqId}.json"

        # 6) Upload original, unchanged body string
        size_bytes = len(body_str.encode("utf-8"))
        if DRY_RUN:
            _log(
                "INFO",
                "Dry-run: would upload",
                requestId=short_reqId,
                appName=app_name,
                timestampMs=ts_ms,
                bucket=RAW_BUCKET_NAME,
                key=key,
                size=size_bytes,
                dryRun=True,
            )
        else:
            try:
                s3 = _get_s3_client()
                s3.put_object(
                    Bucket=RAW_BUCKET_NAME,
                    Key=key,
                    Body=body_str.encode("utf-8"),
                    ContentType="application/json",
                )
                _log(
                    "INFO",
                    "Uploaded analytics payload",
                    requestId=short_reqId,
                    appName=app_name,
                    timestampMs=ts_ms,
                    bucket=RAW_BUCKET_NAME,
                    key=key,
                    size=size_bytes,
                )
            except Exception as s3e:
                _log(
                    "ERROR",
                    "S3 upload failed",
                    requestId=short_reqId,
                    appName=app_name,
                    bucket=RAW_BUCKET_NAME,
                    key=key,
                    error=str(s3e),
                    stack=traceback.format_exc(),
                )
                # Server error for unexpected S3 failures
                return _server_error()

        # 7) Return success
        body = {
            "ok": True,
            "bucket": RAW_BUCKET_NAME,
            "key": key,
            "size": size_bytes,
        }
        if DRY_RUN:
            body["dryRun"] = True
        return _json_response(200, body)

    except ValueError as ve:
        # Expected client-side issues
        _log("ERROR", "Bad request", requestId=short_reqId, error=str(ve))
        return _bad_request(str(ve))
    except Exception as ex:
        # Unexpected server-side issues
        _log("ERROR", "Unhandled error", requestId=short_reqId, error=str(ex), stack=traceback.format_exc())
        return _server_error()
