from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from flask import Flask, jsonify, request

app = Flask(__name__)

DEFAULT_POINTS = 500_000
POINTS_PER_PRODUCT = 1_000
MAX_POINTS = 500_000
DISCOUNT_PER_POINT = 0.01  # monetary value of one discount point


@dataclass
class Client:
    id: int
    name: str
    points: int = DEFAULT_POINTS

    def redeem(self, requested: int) -> int:
        used = max(0, min(requested, self.points))
        self.points -= used
        return used

    def earn(self, awarded: int) -> None:
        self.points = min(MAX_POINTS, self.points + awarded)


@dataclass
class Partner:
    id: int
    name: str


@dataclass
class Product:
    id: int
    partner_id: int
    name: str
    price: float


class Store:
    def __init__(self) -> None:
        self._clients: Dict[int, Client] = {}
        self._partners: Dict[int, Partner] = {}
        self._products: Dict[int, Product] = {}
        self._client_counter = 1
        self._partner_counter = 1
        self._product_counter = 1

    # Client operations
    def register_client(self, name: str) -> Client:
        client = Client(id=self._client_counter, name=name)
        self._clients[client.id] = client
        self._client_counter += 1
        return client

    def get_client(self, client_id: int) -> Client:
        if client_id not in self._clients:
            raise KeyError("Client not found")
        return self._clients[client_id]

    # Partner operations
    def register_partner(self, name: str) -> Partner:
        partner = Partner(id=self._partner_counter, name=name)
        self._partners[partner.id] = partner
        self._partner_counter += 1
        return partner

    def get_partner(self, partner_id: int) -> Partner:
        if partner_id not in self._partners:
            raise KeyError("Partner not found")
        return self._partners[partner_id]

    # Product operations
    def add_product(self, partner_id: int, name: str, price: float) -> Product:
        self.get_partner(partner_id)  # ensures partner exists
        product = Product(id=self._product_counter, partner_id=partner_id, name=name, price=price)
        self._products[product.id] = product
        self._product_counter += 1
        return product

    def list_products(self) -> List[Product]:
        return list(self._products.values())

    def get_product(self, product_id: int) -> Product:
        if product_id not in self._products:
            raise KeyError("Product not found")
        return self._products[product_id]

    # Purchase operations
    def purchase(self, client_id: int, product_id: int, redeem_points: int = 0) -> Dict[str, object]:
        client = self.get_client(client_id)
        product = self.get_product(product_id)

        redeemed = client.redeem(redeem_points)
        discount_amount = round(redeemed * DISCOUNT_PER_POINT, 2)
        final_price = max(product.price - discount_amount, 0.0)

        client.earn(POINTS_PER_PRODUCT)

        return {
            "product": {
                "id": product.id,
                "name": product.name,
                "partner_id": product.partner_id,
            },
            "base_price": product.price,
            "discount_points_used": redeemed,
            "discount_amount": discount_amount,
            "final_price": final_price,
            "points_earned": POINTS_PER_PRODUCT,
            "points_balance": client.points,
        }


store = Store()


def error_response(message: str, status: int = 400):
    return jsonify({"error": message}), status


@app.post("/register/client")
def register_client():
    payload = request.get_json(force=True, silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return error_response("Client name is required")
    client = store.register_client(name)
    return jsonify({"id": client.id, "name": client.name, "points": client.points}), 201


@app.post("/register/partner")
def register_partner():
    payload = request.get_json(force=True, silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return error_response("Partner name is required")
    partner = store.register_partner(name)
    return jsonify({"id": partner.id, "name": partner.name}), 201


@app.post("/products")
def create_product():
    payload = request.get_json(force=True, silent=True) or {}
    try:
        partner_id = int(payload.get("partner_id"))
        name = (payload.get("name") or "").strip()
        price = float(payload.get("price"))
    except (TypeError, ValueError):
        return error_response("Invalid product payload")

    if not name:
        return error_response("Product name is required")
    if price < 0:
        return error_response("Price must be non-negative")

    try:
        product = store.add_product(partner_id=partner_id, name=name, price=price)
    except KeyError:
        return error_response("Partner not found", 404)

    return jsonify({
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "partner_id": product.partner_id,
    }), 201


@app.get("/products")
def list_products():
    products = [
        {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "partner_id": product.partner_id,
        }
        for product in store.list_products()
    ]
    return jsonify(products)


@app.post("/purchase")
def purchase():
    payload = request.get_json(force=True, silent=True) or {}
    try:
        client_id = int(payload.get("client_id"))
        product_id = int(payload.get("product_id"))
        redeem_points = int(payload.get("redeem_points", 0))
    except (TypeError, ValueError):
        return error_response("Invalid purchase payload")

    if redeem_points < 0:
        return error_response("redeem_points cannot be negative")

    try:
        summary = store.purchase(client_id=client_id, product_id=product_id, redeem_points=redeem_points)
    except KeyError as exc:
        return error_response(str(exc), 404)

    return jsonify(summary)


@app.get("/clients/<int:client_id>")
def get_client(client_id: int):
    try:
        client = store.get_client(client_id)
    except KeyError:
        return error_response("Client not found", 404)
    return jsonify({"id": client.id, "name": client.name, "points": client.points})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
