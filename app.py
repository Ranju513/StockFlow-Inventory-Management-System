
from flask import Flask, render_template, request, redirect, url_for, flash
from config import get_db_connection

app = Flask(__name__)
app.secret_key = "stockflow-local-development-key"


# DASHBOARD
@app.route("/")
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            COUNT(*) AS total_products,
            COALESCE(SUM(quantity), 0) AS total_stock,
            SUM(CASE WHEN quantity <= reorder_level THEN 1 ELSE 0 END) AS low_stock
        FROM products
    """)
    inventory = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) AS total_categories FROM categories")
    total_categories = cursor.fetchone()["total_categories"]

    cursor.execute("""
        SELECT p.*, c.category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.category_id
        ORDER BY p.product_id DESC
        LIMIT 8
    """)
    recent_products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        total_products=inventory["total_products"],
        total_categories=total_categories,
        total_stock=inventory["total_stock"],
        low_stock=inventory["low_stock"] or 0,
        recent_products=recent_products
    )


# PRODUCTS
@app.route("/products")
def products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.*, c.category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.category_id
        ORDER BY p.product_id DESC
    """)
    all_products = cursor.fetchall()

    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("products.html", products=all_products, categories=categories)


@app.route("/products/add", methods=["POST"])
def add_product():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO products
            (product_name, category_id, sku, purchase_price, selling_price, quantity)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            request.form["product_name"],
            request.form["category_id"],
            request.form["sku"],
            request.form["purchase_price"],
            request.form["selling_price"],
            request.form["quantity"]
        ))

        conn.commit()
        flash("Product added successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Product error: {e}", "error")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("products"))


@app.route("/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
        conn.commit()
        flash("Product deleted successfully!", "success")

    except Exception:
        conn.rollback()
        flash("Product cannot be deleted because it may have sales records.", "error")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("products"))


# CATEGORIES
@app.route("/categories")
def categories():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.category_id, c.category_name, c.description,
        COUNT(p.product_id) AS product_count
        FROM categories c
        LEFT JOIN products p ON c.category_id = p.category_id
        GROUP BY c.category_id, c.category_name, c.description
        ORDER BY c.category_id DESC
    """)
    all_categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("categories.html", categories=all_categories)


@app.route("/categories/add", methods=["POST"])
def add_category():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO categories (category_name, description)
            VALUES (%s, %s)
        """, (request.form["category_name"], request.form.get("description", "")))

        conn.commit()
        flash("Category added successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Category error: {e}", "error")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("categories"))


@app.route("/categories/delete/<int:category_id>", methods=["POST"])
def delete_category(category_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM products WHERE category_id = %s", (category_id,))

        if cursor.fetchone()[0] > 0:
            flash("Cannot delete a category containing products.", "error")
        else:
            cursor.execute("DELETE FROM categories WHERE category_id = %s", (category_id,))
            conn.commit()
            flash("Category deleted successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Category error: {e}", "error")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("categories"))


# SALES
@app.route("/sales")
def sales():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM products
        WHERE quantity > 0
        ORDER BY product_name
    """)
    products = cursor.fetchall()

    cursor.execute("""
        SELECT s.*, p.product_name
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        ORDER BY s.sale_date DESC
    """)
    all_sales = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("sales.html", products=products, sales=all_sales)


@app.route("/sales/add", methods=["POST"])
def add_sale():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        product_id = int(request.form["product_id"])
        quantity = int(request.form["quantity"])

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        cursor.execute("""
            SELECT * FROM products
            WHERE product_id = %s FOR UPDATE
        """, (product_id,))

        product = cursor.fetchone()

        if not product:
            raise ValueError("Product not found.")

        if quantity > product["quantity"]:
            raise ValueError("Insufficient stock.")

        price = product["selling_price"]
        total = price * quantity

        cursor.execute("""
            INSERT INTO sales
            (product_id, quantity_sold, unit_price, total_amount)
            VALUES (%s, %s, %s, %s)
        """, (product_id, quantity, price, total))

        cursor.execute("""
            UPDATE products
            SET quantity = quantity - %s
            WHERE product_id = %s
        """, (quantity, product_id))

        conn.commit()
        flash("Sale recorded and stock updated!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Sale failed: {e}", "error")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("sales"))


# REPORTS
@app.route("/reports")
def reports():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS total_sales,
        COALESCE(SUM(total_amount), 0) AS revenue
        FROM sales
    """)
    summary = cursor.fetchone()

    cursor.execute("""
        SELECT COALESCE(SUM(
            (s.unit_price - p.purchase_price) * s.quantity_sold
        ), 0) AS estimated_profit
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
    """)
    profit = cursor.fetchone()["estimated_profit"]

    cursor.execute("""
        SELECT s.*, p.product_name
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        ORDER BY s.sale_date DESC
    """)
    sales_history = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "reports.html",
        summary=summary,
        profit=profit,
        sales=sales_history
    )


if __name__ == "__main__":
    app.run(debug=True)
