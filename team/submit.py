import json, sys, time, urllib.error, urllib.request

BASE = "http://127.0.0.1:8000"

def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.headers, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.headers, json.loads(e.read())

path = sys.argv[1] if len(sys.argv) > 1 else "docs/EXAMPLE_REQUEST.json"
body = json.load(open(path, encoding="utf-8"))
body["request_id"] = f"dev-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1000000}"
status, headers, job = call("POST", "/v1/assessments", body)
if status != 202:
    err = job.get("error", {})
    print("rejected", status, err.get("code"), json.dumps(err.get("field_errors", [])))
    sys.exit(1)
while job["job_status"] != "finished":
    time.sleep(0.5)
    _, _, job = call("GET", headers["Location"])
res, diag = job["result"], job["diagnostics"]
print("result_origin ", job["result_origin"])
print("status        ", res["assessment_status"], "| predicted_trl", res["predicted_trl"], "| error_code", res["error_code"])
print("criteria      ", res["criterion_status"])
print("timings_ms    ", diag.get("timings_ms"))
if "failure" in diag:
    print("failure       ", diag["failure"]["message"])
for i in diag.get("output_issues", []):
    print("output issue  ", i["path"], i["rule"])
print("module logs   ", f"server_data/jobs/{job['assessment_id']}/stderr.log")
