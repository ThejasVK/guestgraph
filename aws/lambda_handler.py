"""AWS Lambda entry point: rebuild audiences when new transaction files land in S3.

Trigger: s3:ObjectCreated on  s3://<bucket>/incoming/transactions.csv
Reads:   incoming/transactions.csv and incoming/loyalty_members.csv
Writes:  audiences/<date>/segment_<name>.csv and report.json

Deploy with the SAM template in this folder (`sam build && sam deploy --guided`).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from pathlib import Path

import boto3

from guestgraph.cli import run

s3 = boto3.client("s3")
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "audiences")


def handler(event, context):
    record = event["Records"][0]["s3"]
    bucket, key = record["bucket"]["name"], record["object"]["key"]
    prefix = key.rsplit("/", 1)[0]
    with tempfile.TemporaryDirectory() as tmp:
        data, out = Path(tmp, "data"), Path(tmp, "out")
        data.mkdir()
        out.mkdir()
        for name in ("transactions.csv", "loyalty_members.csv"):
            s3.download_file(bucket, f"{prefix}/{name}", str(data / name))
        report = run(data, out)
        stamp = dt.date.today().isoformat()
        for f in out.glob("*.csv"):
            s3.upload_file(str(f), bucket, f"{OUTPUT_PREFIX}/{stamp}/{f.name}")
        s3.put_object(Bucket=bucket, Key=f"{OUTPUT_PREFIX}/{stamp}/report.json",
                      Body=json.dumps(report, default=str).encode())
    return {"statusCode": 200, "body": json.dumps({k: report[k] for k in ("guests", "resolution_rate")})}
