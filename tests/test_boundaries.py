def test_local_boundary_and_private_storage(workspace):
    client = workspace.client
    assert client.get("/").status_code == 200
    assert client.get("/data/workspace.sqlite3").status_code == 404
    assert client.get("/platform_core.py").status_code == 404
    assert client.get("/", headers={"Origin": "https://attacker.invalid"}).status_code == 403
    assert client.get("/", headers={"Host": "attacker.invalid"}).status_code == 403
    assert client.get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.get("/").headers["x-frame-options"] == "DENY"


def test_mutations_require_request_header(workspace):
    client = workspace.client
    request = client.build_request("POST", "/api/not-a-route")
    del request.headers["x-workspace"]
    assert client.send(request).status_code == 403
