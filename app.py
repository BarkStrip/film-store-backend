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
        select film.film_id, film.title, description, release_year, film.rental_duration, film.rental_rate, CAST(film.special_features AS CHAR) AS special_features, film.replacement_cost, film.last_update, length, rating, count(*) as rented
        from film
        join inventory on film.film_id = inventory.film_id
        join rental on inventory.inventory_id = rental.inventory_id
        group by film.film_id
        order by count(*) DESC
        limit 5;
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/top-actors", methods=["GET"])
def top_actors():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        select actor.actor_id, actor.first_name, actor.last_name, actor.last_update, count(*) as movies
        from actor
        join film_actor on actor.actor_id = film_actor.actor_id
        group by actor.actor_id
        order by count(*) desc
        limit 5;
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

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3001, debug=True)