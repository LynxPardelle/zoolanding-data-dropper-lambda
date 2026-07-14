import json
import unittest

import lambda_function


class LambdaContext:
    aws_request_id = "12345678-aaaa-bbbb-cccc-1234567890ab"


class FakeS3Client:
    def __init__(self):
        self.put_object_calls = []

    def put_object(self, **kwargs):
        self.put_object_calls.append(kwargs)


class DataDropperLambdaTests(unittest.TestCase):
    def setUp(self):
        self.original_dry_run = lambda_function.DRY_RUN
        self.original_bucket_name = lambda_function.RAW_BUCKET_NAME
        self.original_log_level = lambda_function.LOG_LEVEL
        self.original_log = lambda_function._log
        self.original_s3 = lambda_function.S3
        lambda_function.RAW_BUCKET_NAME = "unit-test-bucket"
        lambda_function.LOG_LEVEL = "ERROR"
        lambda_function._log = lambda *args, **kwargs: None
        lambda_function.S3 = None

    def tearDown(self):
        lambda_function.DRY_RUN = self.original_dry_run
        lambda_function.RAW_BUCKET_NAME = self.original_bucket_name
        lambda_function.LOG_LEVEL = self.original_log_level
        lambda_function._log = self.original_log
        lambda_function.S3 = self.original_s3

    def _event_for(self, body):
        return {
            "isBase64Encoded": False,
            "body": body,
        }

    def test_response_includes_local_event_time_when_timezone_is_present(self):
        lambda_function.DRY_RUN = True
        payload = {
            "appName": "zoo_landing_page",
            "timestamp": 1756272600000,
            "timezone": "America/Mexico_City",
            "name": "page_view",
        }

        response = lambda_function.lambda_handler(self._event_for(json.dumps(payload)), LambdaContext())
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertNotIn("bucket", body)
        self.assertNotIn("key", body)
        self.assertEqual(body["eventTime"]["timestampMs"], 1756272600000)
        self.assertEqual(body["eventTime"]["utc"], "2025-08-27T05:30:00Z")
        self.assertEqual(body["eventTime"]["timezone"], "America/Mexico_City")
        self.assertEqual(body["eventTime"]["local"], "2025-08-26T23:30:00-06:00")
        self.assertEqual(body["eventTime"]["localDate"], "2025-08-26")
        self.assertEqual(body["eventTime"]["localHour"], "23")

    def test_upload_adds_event_time_metadata_without_rewriting_body(self):
        lambda_function.DRY_RUN = False
        fake_s3 = FakeS3Client()
        lambda_function.S3 = fake_s3
        raw_body = json.dumps(
            {
                "appName": "zoo_landing_page",
                "timestamp": 1756272600000,
                "timezone": "America/Mexico_City",
                "name": "cta_click",
            },
            separators=(",", ":"),
        )

        response = lambda_function.lambda_handler(self._event_for(raw_body), LambdaContext())
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["ok"], True)
        self.assertEqual(len(fake_s3.put_object_calls), 1)
        upload = fake_s3.put_object_calls[0]
        self.assertEqual(
            upload["Key"],
            "zoo_landing_page/2025/08/27/1756272600000-567890ab.json",
        )
        self.assertEqual(upload["Body"], raw_body.encode("utf-8"))
        self.assertEqual(upload["Metadata"]["timestamp-ms"], "1756272600000")
        self.assertEqual(upload["Metadata"]["event-time-utc"], "2025-08-27T05:30:00Z")
        self.assertEqual(upload["Metadata"]["event-timezone"], "America/Mexico_City")
        self.assertEqual(upload["Metadata"]["event-time-local"], "2025-08-26T23:30:00-06:00")
        self.assertEqual(upload["Metadata"]["event-local-date"], "2025-08-26")
        self.assertEqual(upload["Metadata"]["event-local-hour"], "23")

    def test_seconds_timestamp_still_normalizes_to_utc_key(self):
        lambda_function.DRY_RUN = False
        fake_s3 = FakeS3Client()
        lambda_function.S3 = fake_s3
        payload = {
            "appName": "zoolanding-web",
            "timestamp": 1725148800,
        }

        response = lambda_function.lambda_handler(self._event_for(json.dumps(payload)), LambdaContext())
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertNotIn("key", body)
        self.assertEqual(
            fake_s3.put_object_calls[0]["Key"],
            "zoolanding-web/2024/09/01/1725148800000-567890ab.json",
        )
        self.assertEqual(body["eventTime"], {"timestampMs": 1725148800000, "utc": "2024-09-01T00:00:00Z"})

    def test_invalid_optional_timezone_does_not_drop_raw_event(self):
        lambda_function.DRY_RUN = True
        payload = {
            "appName": "zoolanding-web",
            "timestamp": 1725148800000,
            "timezone": "Mars/Base",
        }

        response = lambda_function.lambda_handler(self._event_for(json.dumps(payload)), LambdaContext())
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["ok"], True)
        self.assertEqual(body["eventTime"], {"timestampMs": 1725148800000, "utc": "2024-09-01T00:00:00Z"})

    def test_valid_json_must_be_an_object(self):
        lambda_function.DRY_RUN = True

        response = lambda_function.lambda_handler(self._event_for("[]"), LambdaContext())
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body, {"ok": False, "error": "Body JSON must be an object"})

    def test_blog_event_requires_hub_and_article_ids(self):
        lambda_function.DRY_RUN = True
        payload = {
            "appName": "zoolanding-web",
            "timestamp": 1725148800000,
            "name": "blog_view",
            "feature": "blog",
            "contentHubId": "main",
            "articleId": "primer-post",
        }

        response = lambda_function.lambda_handler(self._event_for(json.dumps(payload)), LambdaContext())
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["ok"], True)
        self.assertNotIn("bucket", body)
        self.assertNotIn("key", body)

    def test_blog_event_accepts_runtime_meta_ids(self):
        lambda_function.DRY_RUN = True
        payload = {
            "appName": "zoolanding-web",
            "timestamp": 1725148800000,
            "name": "blog_view",
            "feature": "blog",
            "meta": {
                "hubId": "zoosite-main",
                "articleId": "art_runtime_public",
                "category": "web",
                "tags": ["seo", "builder"],
                "path": "/blog/web/runtime-public",
            },
        }

        response = lambda_function.lambda_handler(self._event_for(json.dumps(payload)), LambdaContext())
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["ok"], True)

    def test_blog_event_rejects_sensitive_fields(self):
        lambda_function.DRY_RUN = True
        payload = {
            "appName": "zoolanding-web",
            "timestamp": 1725148800000,
            "name": "blog_comment_submit",
            "feature": "blog",
            "contentHubId": "main",
            "articleId": "primer-post",
            "email": "reader@example.com",
        }

        response = lambda_function.lambda_handler(self._event_for(json.dumps(payload)), LambdaContext())
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body["error"], "Blog analytics events must not include 'email'")

    def test_blog_event_rejects_nested_sensitive_fields_and_values(self):
        lambda_function.DRY_RUN = True
        payload = {
            "appName": "zoolanding-web",
            "timestamp": 1725148800000,
            "name": "blog_view",
            "feature": "blog",
            "contentHubId": "main",
            "articleId": "primer-post",
            "metadata": {
                "reader": {
                    "contact": "reader@example.com",
                },
            },
        }

        response = lambda_function.lambda_handler(self._event_for(json.dumps(payload)), LambdaContext())
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body["error"], "Blog analytics events must not include private values")

    def test_blog_event_rejects_sensitive_values_inside_runtime_meta(self):
        lambda_function.DRY_RUN = True
        payload = {
            "appName": "zoolanding-web",
            "timestamp": 1725148800000,
            "name": "blog_view",
            "feature": "blog",
            "meta": {
                "hubId": "zoosite-main",
                "articleId": "art_runtime_public",
                "reader": "reader@example.com",
            },
        }

        response = lambda_function.lambda_handler(self._event_for(json.dumps(payload)), LambdaContext())
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body["error"], "Blog analytics events must not include private values")


if __name__ == "__main__":
    unittest.main()
