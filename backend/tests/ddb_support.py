"""Shared DynamoDB test backend.

Creates the tables from the SAM ``template.yaml`` — so tests exercise the exact
schema the deploy provisions. A GSI added to the template becomes available to tests
automatically; a GSI the code queries but the template lacks fails these tests rather
than production. This replaces a hand-maintained copy of the schema that could (and
would, as tables multiply) silently drift from the template.

Backend selection: moto by default (in-process, fast, already a dev dep). If
``WP_DDB_ENDPOINT_URL`` is set the tables are created against that endpoint instead —
DynamoDB Local in CI — so the same suite runs against AWS's own engine, which matters
for transaction / conditional-write fidelity that moto only approximates.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import boto3
import yaml

TEMPLATE = Path(__file__).resolve().parents[2] / "template.yaml"
PREFIX = "test-"
REGION = "us-east-1"

# create_table only accepts these keys; the template's Properties carry no others for
# our tables today, but list them explicitly so an added Property can't leak through.
_CREATE_TABLE_KEYS = (
    "TableName",
    "BillingMode",
    "AttributeDefinitions",
    "KeySchema",
    "GlobalSecondaryIndexes",
)


class _CfnLoader(yaml.SafeLoader):
    """A YAML loader that tolerates CloudFormation intrinsics (``!Sub``, ``!Ref``, …).

    We only read the DynamoDB tables' plain Properties; the one intrinsic that reaches
    them is ``!Sub "${TablePrefix}Name"`` on TableName, which we resolve by hand below.
    Every other ``!Tag`` is reduced to its underlying scalar/list/map and ignored.
    """


def _cfn_passthrough(loader: yaml.Loader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_CfnLoader.add_multi_constructor("!", _cfn_passthrough)


def set_env(monkeypatch, *, prefix: str = PREFIX, region: str = REGION) -> None:
    """Point settings at the test Dynamo backend. The caller clears the settings
    cache afterward so the new env is read (settings are lru-cached)."""
    monkeypatch.setenv("WP_PERSISTENCE", "dynamo")
    monkeypatch.setenv("WP_DDB_TABLE_PREFIX", prefix)
    monkeypatch.setenv("WP_AWS_REGION", region)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", region)


def table_specs(prefix: str = PREFIX) -> list[dict[str, Any]]:
    """create_table kwargs for every ``AWS::DynamoDB::Table`` in the template."""
    doc = yaml.load(TEMPLATE.read_text(), Loader=_CfnLoader)
    specs: list[dict[str, Any]] = []
    for res in doc.get("Resources", {}).values():
        if res.get("Type") != "AWS::DynamoDB::Table":
            continue
        props = res["Properties"]
        name = props["TableName"].replace("${TablePrefix}", prefix)
        spec = {k: props[k] for k in _CREATE_TABLE_KEYS if k in props}
        spec["TableName"] = name
        specs.append(spec)
    return specs


def _drop_all(client, prefix: str) -> None:
    for name in client.list_tables().get("TableNames", []):
        if name.startswith(prefix):
            client.delete_table(TableName=name)
            client.get_waiter("table_not_exists").wait(TableName=name)


@contextmanager
def dynamo_backend(prefix: str = PREFIX) -> Iterator[None]:
    """Provision the template's tables for one test, then tear them down.

    moto unless ``WP_DDB_ENDPOINT_URL`` is set, in which case a real DynamoDB Local is
    used (tables are dropped before and after so each test starts from empty)."""
    endpoint = os.environ.get("WP_DDB_ENDPOINT_URL")
    if endpoint:
        client = boto3.client("dynamodb", region_name=REGION, endpoint_url=endpoint)
        _drop_all(client, prefix)
        for spec in table_specs(prefix):
            client.create_table(**spec)
        try:
            yield
        finally:
            _drop_all(client, prefix)
    else:
        from moto import mock_aws

        with mock_aws():
            client = boto3.client("dynamodb", region_name=REGION)
            for spec in table_specs(prefix):
                client.create_table(**spec)
            yield
