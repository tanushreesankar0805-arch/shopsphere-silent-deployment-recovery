
import os

from flask import (
    Flask,
    jsonify,
    request,
    Response,
    render_template
)

from prometheus_client import (
    Counter,
    generate_latest,
    CONTENT_TYPE_LATEST
)


# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

app = Flask(__name__)

VERSION = os.getenv("APP_VERSION", "v1")

PRODUCTS = {
    "headphones": 1500,
    "keyboard": 2000,
    "mouse": 800
}


# --------------------------------------------------
# PROMETHEUS METRICS
# --------------------------------------------------

checkout_requests = Counter(
    "shopsphere_checkout_requests_total",
    "Total checkout requests grouped by version and result",
    ["version", "status"]
)

# Initialize metric series for Grafana.
checkout_requests.labels(
    version=VERSION,
    status="success"
)

checkout_requests.labels(
    version=VERSION,
    status="failed"
)


# --------------------------------------------------
# SHOPSPHERE WEBSITE
# --------------------------------------------------

@app.get("/")
def home():
    return render_template("shop.html")


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health():
    return jsonify({
        "status": "healthy",
        "version": VERSION
    })


# --------------------------------------------------
# PRODUCT API
# --------------------------------------------------

@app.get("/products")
def products():
    return jsonify(PRODUCTS)


# --------------------------------------------------
# PROMETHEUS METRICS ENDPOINT
# --------------------------------------------------

@app.get("/metrics")
def metrics():
    return Response(
        generate_latest(),
        content_type=CONTENT_TYPE_LATEST
    )


# --------------------------------------------------
# CHECKOUT API
# --------------------------------------------------

@app.post("/checkout")
def checkout():

    data = request.get_json(silent=True) or {}

    product = data.get("product")
    discount = data.get("discount", 0)

    # --------------------------------------------------
    # VALIDATE PRODUCT
    # --------------------------------------------------

    if product not in PRODUCTS:

        checkout_requests.labels(
            version=VERSION,
            status="failed"
        ).inc()

        return jsonify({
            "status": "failed",
            "error": "Invalid product",
            "version": VERSION
        }), 400

    # --------------------------------------------------
    # VALIDATE DISCOUNT
    # --------------------------------------------------

    if (
        type(discount) not in (int, float)
        or not 0 <= discount <= 100
    ):

        checkout_requests.labels(
            version=VERSION,
            status="failed"
        ).inc()

        return jsonify({
            "status": "failed",
            "error": "Invalid discount",
            "version": VERSION
        }), 400

    # --------------------------------------------------
    # CALCULATE EXPECTED CHECKOUT PRICE
    # --------------------------------------------------

    price = PRODUCTS[product]

    expected_price = round(
        price * (1 - discount / 100),
        2
    )

    # --------------------------------------------------
    # SILENT BUSINESS-LOGIC REGRESSION SIMULATION
    # --------------------------------------------------
    #
    # V1:
    # Correctly applies the discount.
    #
    # V2:
    # Returns HTTP 200 and reports success,
    # but fails to apply the discount.
    #
    # Example:
    # Headphones = 1500
    # Discount = 10%
    #
    # V1 final price = 1350
    # V2 final price = 1500 (incorrect)
    #
    # Both health endpoints remain healthy.
    # --------------------------------------------------

    if VERSION == "v2" and discount > 0:
        final_price = price
    else:
        final_price = expected_price

    # --------------------------------------------------
    # RECORD SUCCESSFUL HTTP CHECKOUT
    # --------------------------------------------------
    #
    # V2 still reports success because the
    # application does not recognize its own
    # incorrect business calculation.
    # --------------------------------------------------

    checkout_requests.labels(
        version=VERSION,
        status="success"
    ).inc()

    # --------------------------------------------------
    # RETURN CHECKOUT RESPONSE
    # --------------------------------------------------

    return jsonify({
        "status": "success",
        "message": "Order placed successfully!",
        "product": product,
        "original_price": price,
        "discount": discount,
        "final_price": final_price,
        "version": VERSION
    }), 200


# --------------------------------------------------
# APPLICATION STARTUP
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
