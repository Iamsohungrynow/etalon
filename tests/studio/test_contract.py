"""The U1 contract (plan-u1 §13): every route is registered, the 501 stubs name themselves."""

import pytest

from etalon.studio.openapi import build_schema

U1_ROUTES = [
    ("get", "/api/templates"),
    ("post", "/api/simulations"),
    ("get", "/api/simulations/{id}/spec"),
    ("get", "/api/simulations/{id}/permittivity"),
    ("post", "/api/simulations/{id}/open"),
    ("post", "/api/calibrate"),
    ("post", "/api/simulations/{id}/run"),
    ("delete", "/api/jobs/{job_id}"),
    ("get", "/api/results/{id}"),
    ("get", "/api/results/{id}/fields/{monitor}"),
    ("get", "/api/results/{id}/spectra/{monitor}"),
]

STUBS = [
    ("put", "/api/simulations/{id}/params", "/api/simulations/abc/params", "U1 + et.param"),
    ("get", "/api/results/{id}/s-matrix", "/api/results/abc~1/s-matrix", "M2"),
    ("get", "/api/results/{id}/modes/{monitor}", "/api/results/abc~1/modes/thru", "M1"),
    ("post", "/api/modes/solve", "/api/modes/solve", "M1"),
    ("get", "/api/validation/latest", "/api/validation/latest", "U4"),
    ("post", "/api/validation/run", "/api/validation/run", "U4"),
]


@pytest.fixture(scope="module")
def schema():
    return build_schema()


@pytest.mark.parametrize(("method", "path"), U1_ROUTES + [(m, p) for m, p, _, _ in STUBS])
def test_every_route_of_the_contract_is_in_the_schema(schema, method, path):
    assert method in schema["paths"][path]


@pytest.mark.parametrize(
    "name",
    [
        # WebSocket messages and binary headers are no route's body; they are added.
        "JobMessage",
        "StartedMessage",
        "HistoryMessage",
        "Progress",
        "LogLine",
        "DoneMessage",
        "ArrayHeader",
        "PermittivityHeader",
        "FieldHeader",
        "SnapshotHeader",
        # Route bodies
        "SimulationSpec",
        "Preview",
        "Estimate",
        "Warning",
        "ScriptError",
        "Template",
        "JobStarted",
        "ResultMeta",
        "Spectra",
    ],
)
def test_contract_types_reach_the_schema(schema, name):
    assert name in schema["components"]["schemas"]


def test_simulation_row_gains_job_and_result_ids(schema):
    row = schema["components"]["schemas"]["SimulationRow"]["properties"]
    assert {"job_id", "last_result_id"} <= set(row)


def test_binary_routes_declare_octet_stream(schema):
    for path in ("/api/simulations/{id}/permittivity", "/api/results/{id}/fields/{monitor}"):
        content = schema["paths"][path]["get"]["responses"]["200"]["content"]
        assert list(content) == ["application/octet-stream"]


@pytest.mark.parametrize(("method", "_", "url", "arrives_in"), STUBS)
def test_501_stubs_name_their_endpoint(client, method, _, url, arrives_in):
    response = client.request(method.upper(), url)
    assert response.status_code == 501
    body = response.json()
    assert body["code"] == "not_implemented"
    assert body["endpoint"] == f"{method.upper()} {_}"
    assert body["arrives_in"] == arrives_in
