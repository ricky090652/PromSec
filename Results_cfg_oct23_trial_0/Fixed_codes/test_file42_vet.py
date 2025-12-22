import os
from flask import Flask, request, jsonify
import mysql.connector

app = Flask(__name__)

db_user = os.getenv("DB_USER", "root")
db_password = os.getenv("DB_PASSWORD", "password")
db_host = os.getenv("DB_HOST", "localhost")
db_name = "library_db"

db = mysql.connector.connect(
    host=db_host,
    user=db_user,
    password=db_password,
    database=db_name
)
cursor = db.cursor()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()

    if result:
        return jsonify({"message": "Username already exists"})
    else:
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        db.commit()
        return jsonify({"message": "User registered successfully"})

@app.route('/checkout', methods=['POST'])
def checkout():
    data = request.get_json()
    username = data.get('username')
    book_id = data.get('book_id')

    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()

    if not result:
        return jsonify({"message": "User not found"})
    
    cursor.execute("INSERT INTO checkouts (username, book_id) VALUES (%s, %s)", (username, book_id))
    db.commit()
    return jsonify({"message": "Book checked out successfully"})

@app.route('/return', methods=['POST'])
def return_book():
    data = request.get_json()
    username = data.get('username')
    book_id = data.get('book_id')

    cursor.execute("SELECT * FROM checkouts WHERE username = %s AND book_id = %s", (username, book_id))
    result = cursor.fetchone()

    if not result:
        return jsonify({"message": "Checkout record not found"})
    
    cursor.execute("DELETE FROM checkouts WHERE username = %s AND book_id = %s", (username, book_id))
    db.commit()
    return jsonify({"message": "Book returned successfully"})

if __name__ == '__main__':
    app.run(debug=False)