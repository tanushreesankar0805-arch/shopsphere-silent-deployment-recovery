
import threading
import requests

from flask import Flask, jsonify, request, Response

app = Flask(__name__)

BACKENDS = {
    "v1": "http://shopsphere-v1:5000",
    "v2": "http://shopsphere-v2:5000"
}

active_version = "v1"
release_generation = 0

lock = threading.Lock()


@app.get("/router/status")
def status():
    with lock:
        return jsonify({
            "active_version": active_version,
            "backend": BACKENDS[active_version],
            "release_generation": release_generation
        })


@app.post("/router/switch/<version>")
def switch(version):
    global active_version, release_generation

    if version not in BACKENDS:
        return jsonify({
            "error": "Unknown version"
        }), 400

    data = request.get_json(silent=True) or {}
    expected_generation = data.get("expected_generation")

    with lock:

        # Reject outdated release decisions.
        if (
            expected_generation is not None
            and expected_generation != release_generation
        ):
            return jsonify({
                "error": "Release generation conflict",
                "current_generation": release_generation
            }), 409

        if active_version == version:
            return jsonify({
                "message": "Release already active",
                "active_version": active_version,
                "release_generation": release_generation
            })

        previous_version = active_version

        active_version = version
        release_generation += 1

        app.logger.warning(
            "RELEASE SWITCH: %s -> %s | generation=%d",
            previous_version,
            version,
            release_generation
        )

        return jsonify({
            "message": "Traffic switched",
            "previous_version": previous_version,
            "active_version": active_version,
            "release_generation": release_generation
        })


@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def proxy(path):

    with lock:
        version = active_version

    url = f"{BACKENDS[version]}/{path}"

    try:
        response = requests.request(
            method=request.method,
            url=url,
            params=request.args,
            json=(
                request.get_json(silent=True)
                if request.method == "POST"
                else None
            ),
            timeout=5
        )

        return Response(
            response.content,
            status=response.status_code,
            content_type=response.headers.get(
                "Content-Type",
                "application/json"
            )
        )

    except requests.RequestException:
        return jsonify({
            "error": "Backend unavailable",
            "active_version": version
        }), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080,
        threaded=True
    )
