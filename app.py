from flask import Flask, jsonify
import mysql.connector
import os
from dotenv import load_dotenv
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # all routes, all origins
load_dotenv(dotenv_path=".env.local")

def get_conn():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

@app.route('/api/hello')
def hello():
    return jsonify(message="Hello From Flask!")

# --- 1) top 5 rented films of all times --- 
@app.route("/api/top-films", methods=["GET"])
def top_films():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT  f.film_id,
                f.title,
                f.description,
                f.release_year,
                f.rental_duration,
                f.rental_rate,
                CAST(f.special_features AS CHAR) AS special_features,
                f.replacement_cost,
                f.last_update,
                f.length,
                f.rating,
                COUNT(DISTINCT r.rental_id) AS rented,
                COUNT(DISTINCT CASE
                    WHEN i.inventory_id IS NOT NULL
                    AND (r2.rental_id IS NULL OR r2.return_date IS NOT NULL)
                    THEN i.inventory_id
                END) AS available_inventory
        FROM film f
        JOIN inventory i ON f.film_id = i.film_id
        JOIN rental r ON i.inventory_id = r.inventory_id
        LEFT JOIN rental r2 ON i.inventory_id = r2.inventory_id AND r2.return_date IS NULL
        GROUP BY f.film_id
        ORDER BY COUNT(DISTINCT r.rental_id) DESC
        LIMIT 5;
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/top-actors", methods=["GET"])
def top_actors():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT actor.actor_id, actor.first_name, actor.last_name, actor.last_update, count(*) AS movies
        FROM actor
        JOIN film_actor on actor.actor_id = film_actor.actor_id
        GROUP BY  actor.actor_id
        ORDER BY count(*) desc
        LIMIT 5;
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/<actor_id>", methods=["GET"])
def view_actor_details(actor_id):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT 
            f.title,
            COUNT(r.rental_id) AS times_rented
        FROM film f
        JOIN film_actor fa ON f.film_id = fa.film_id
        JOIN inventory i ON f.film_id = i.film_id
        JOIN rental r ON i.inventory_id = r.inventory_id
        WHERE fa.actor_id = %s
        GROUP BY f.film_id, f.title
        ORDER BY times_rented DESC
        LIMIT 5;
    """, (actor_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/films/", defaults={"search": None}, methods=["GET"])
@app.route("/api/films/<search>", methods=["GET"])
def films(search):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    base_query = """
    SELECT f.film_id,
       f.title,
       f.description,
       f.release_year,
       f.rental_duration,
       f.rental_rate,
       CAST(f.special_features AS CHAR) AS special_features,
       f.replacement_cost,
       f.last_update,
       f.length,
       f.rating,
       c.name AS category,
       COUNT(DISTINCT r.rental_id) AS rented,
       COUNT(DISTINCT CASE
           WHEN i.inventory_id IS NOT NULL
           AND (r.rental_id IS NULL OR r.return_date IS NOT NULL)
           THEN i.inventory_id
       END) AS available_inventory
    FROM film f
    JOIN film_category fc ON f.film_id = fc.film_id
    JOIN category c ON fc.category_id = c.category_id
    LEFT JOIN inventory i ON f.film_id = i.film_id
    LEFT JOIN rental r ON i.inventory_id = r.inventory_id AND r.return_date IS NULL
    LEFT JOIN film_actor fa ON f.film_id = fa.film_id
    LEFT JOIN actor a ON fa.actor_id = a.actor_id

    """

    params = ()
    where_clause = ""
    if search:
        where_clause = """
        WHERE f.title LIKE %s
           OR a.first_name LIKE %s
           OR a.last_name LIKE %s
           OR c.name LIKE %s
        """
        like_term = f"%{search}%"
        params = (like_term, like_term, like_term, like_term)

    group_clause = "GROUP BY f.film_id, c.name"

    final_query = base_query + where_clause + group_clause

    cur.execute(final_query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/api/customers", methods=["POST"])
def create_customer():
    from flask import request
    data = request.get_json()

    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    address_id = data.get('address_id', 1)  # Default to 1
    store_id = data.get('store_id', 1)  # Default to 1

    if not first_name or not last_name or not email:
        return jsonify({"error": "first_name, last_name, and email are required"}), 400

    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    try:
        # Insert new customer
        cur.execute("""
            INSERT INTO customer (store_id, first_name, last_name, email, address_id, active, create_date)
            VALUES (%s, %s, %s, %s, %s, 1, NOW());
        """, (store_id, first_name, last_name, email, address_id))

        conn.commit()
        customer_id = cur.lastrowid

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "customer_id": customer_id,
            "message": "Customer created successfully"
        }), 201

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/customers/<customer_id>", methods=["PUT"])
def update_customer(customer_id):
    from flask import request
    data = request.get_json()

    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')

    if not first_name or not last_name or not email:
        return jsonify({"error": "first_name, last_name, and email are required"}), 400

    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    try:
        # Check if customer exists
        cur.execute("SELECT customer_id FROM customer WHERE customer_id = %s", (customer_id,))
        customer = cur.fetchone()

        if not customer:
            cur.close()
            conn.close()
            return jsonify({"error": "Customer not found"}), 404

        # Update customer
        cur.execute("""
            UPDATE customer
            SET first_name = %s, last_name = %s, email = %s, last_update = NOW()
            WHERE customer_id = %s;
        """, (first_name, last_name, email, customer_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Customer updated successfully"
        }), 200

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/customers/", defaults={"search": None}, methods=["GET"])
@app.route("/api/customers/<search>", methods=["GET"])
def customers(search):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    base_query = """
        SELECT
            C.last_update,
            C.create_date,
            C.active,
            C.address_id,
            C.email,
            C.last_name,
            C.first_name,
            C.store_id,
            C.customer_id
        FROM CUSTOMER C
    """

    params = ()
    where_clause = ""
    if search:
        where_clause = """
        WHERE C.customer_id LIKE %s
           OR C.first_name LIKE %s
           OR C.last_name LIKE %s
           OR C.email LIKE %s
        """
        like_term = f"%{search}%"
        params = (like_term, like_term, like_term, like_term)

    final_query = base_query + where_clause

    cur.execute(final_query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/api/customers/<customer_id>/rentals", methods=["GET"])
def customer_rentals(customer_id):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT
            f.title,
            f.film_id,
            r.rental_id,
            r.rental_date,
            r.return_date,
            CASE
                WHEN r.return_date IS NULL THEN 'Currently Rented'
                ELSE 'Returned'
            END AS status
        FROM rental r
        JOIN inventory i ON r.inventory_id = i.inventory_id
        JOIN film f ON i.film_id = f.film_id
        WHERE r.customer_id = %s
        ORDER BY r.rental_date DESC
        LIMIT 50;
    """, (customer_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/api/rentals", methods=["POST"])
def create_rental():
    from flask import request
    data = request.get_json()

    customer_id = data.get('customer_id')
    film_id = data.get('film_id')

    if not customer_id or not film_id:
        return jsonify({"error": "customer_id and film_id are required"}), 400

    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    try:
        # Find available inventory for this film (not currently rented)
        cur.execute("""
            SELECT i.inventory_id
            FROM inventory i
            LEFT JOIN rental r ON i.inventory_id = r.inventory_id
                AND r.return_date IS NULL
            WHERE i.film_id = %s
                AND r.rental_id IS NULL
            LIMIT 1;
        """, (film_id,))

        inventory = cur.fetchone()

        if not inventory:
            cur.close()
            conn.close()
            return jsonify({"error": "No available inventory for this film"}), 404

        inventory_id = inventory['inventory_id']

        # Create rental record
        cur.execute("""
            INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id)
            VALUES (NOW(), %s, %s, 1);
        """, (inventory_id, customer_id))

        conn.commit()
        rental_id = cur.lastrowid

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "rental_id": rental_id,
            "message": "Rental created successfully"
        }), 201

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/rentals/<rental_id>/return", methods=["PUT"])
def return_rental(rental_id):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    try:
        # Check if rental exists and is not already returned
        cur.execute("""
            SELECT rental_id, return_date
            FROM rental
            WHERE rental_id = %s;
        """, (rental_id,))

        rental = cur.fetchone()

        if not rental:
            cur.close()
            conn.close()
            return jsonify({"error": "Rental not found"}), 404

        if rental['return_date'] is not None:
            cur.close()
            conn.close()
            return jsonify({"error": "Rental already returned"}), 400

        # Update return_date to current timestamp
        cur.execute("""
            UPDATE rental
            SET return_date = NOW()
            WHERE rental_id = %s;
        """, (rental_id,))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Rental returned successfully"
        }), 200

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/customers/<customer_id>", methods=["DELETE"])
def delete_customer(customer_id):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    try:
        # Check if customer exists
        cur.execute("SELECT customer_id FROM customer WHERE customer_id = %s", (customer_id,))
        customer = cur.fetchone()

        if not customer:
            cur.close()
            conn.close()
            return jsonify({"error": "Customer not found"}), 404

        # Delete associated rentals first to avoid foreign key constraints
        cur.execute("DELETE FROM rental WHERE customer_id = %s", (customer_id,))

        # Delete the customer
        cur.execute("DELETE FROM customer WHERE customer_id = %s", (customer_id,))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Customer and associated rentals deleted successfully"
        }), 200

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3001, debug=True)

