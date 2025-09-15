from flask import Flask, jsonify
from flask_cors import CORS
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.local")

def get_conn():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

app = Flask(__name__)
CORS(app)  # this enables CORS for all routes

@app.route('/api/hello')
def hello():
    return jsonify(message="Hello From Flask!")

# --- 1) top 5 rented films of all times --- 
@app.route("/api/top-films", methods=["GET"])
def top_films():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
    select film.title, count(*) as rented
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

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)