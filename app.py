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
        SELECT  film.film_id, 
                film.title, 
                description,
                release_year, 
                film.rental_duration, 
                film.rental_rate, 
                CAST(film.special_features AS CHAR) AS special_features, 
                film.replacement_cost, 
                film.last_update, 
                length, 
                rating, 
                count(*) as rented
        FROM film
        JOIN inventory on film.film_id = inventory.film_id
        JOIN rental on inventory.inventory_id = rental.inventory_id
        GROUP BY film.film_id
        ORDER BY count(*) DESC
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
       COUNT(DISTINCT r.rental_id) AS rented
    FROM film f
    JOIN film_category fc ON f.film_id = fc.film_id
    JOIN category c ON fc.category_id = c.category_id
    LEFT JOIN inventory i ON f.film_id = i.film_id
    LEFT JOIN rental r ON i.inventory_id = r.inventory_id
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


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3001, debug=True)