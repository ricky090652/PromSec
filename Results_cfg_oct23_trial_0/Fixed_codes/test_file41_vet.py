import os
from flask import Flask, request, jsonify
import MySQLdb

app = Flask(__name__)

DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
DB_DATABASE = os.getenv('DB_DATABASE', 'cwe_900')

def db_connection():
    return MySQLdb.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_DATABASE)

@app.route('/register', methods=['POST'])
def register():
    try:
        username = request.form.get('username')
        password = request.form.get('password')

        db = db_connection()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({'message': 'Username already exists'}), 400

        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        db.commit()

        cursor.close()
        db.close()

        return jsonify({'message': 'Registration successful'}), 200

    except Exception as e:
        return jsonify({'message': 'An error occurred'}), 500

if __name__ == '__main__':
    app.run(debug=False)