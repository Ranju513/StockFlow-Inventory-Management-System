
from flask import Blueprint, render_template, request, redirect, url_for, flash
from config import get_db_connection

products_bp = Blueprint("products", __name__)

@products_bp.route("/products")
def products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.*, c.category_name
        FROM products p
        LEFT JOIN categories c
        ON p.category_id = c.category_id
        ORDER BY p.product_id DESC
    """)

    all_products = cursor.fetchall()

    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "products.html",
        products=all_products,
        categories=categories
    )

@products_bp.route("/products/add", methods=["POST"])
def add_product():

    name = request.form["product_name"]
    category = request.form["category_id"]
    sku = request.form["sku"]
    purchase = request.form["purchase_price"]
    selling = request.form["selling_price"]
    quantity = request.form["quantity"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products
        (product_name, category_id, sku,
        purchase_price, selling_price, quantity)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (name, category, sku, purchase, selling, quantity))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("products.products"))
