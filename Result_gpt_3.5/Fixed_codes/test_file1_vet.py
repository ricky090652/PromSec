from flask import Flask, request
import hashlib
import os
import mysql.connector

app = Flask(__name__)

db = mysql.connector.connect(
    host=os.environ.get('DB_HOST'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD'),
    database=os.environ.get('DB_NAME')
)
cursor = db.cursor()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user:
        return 'User already exists', 400

    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)

    cursor.execute("INSERT INTO users (username, password, salt) VALUES (%s, %s, %s)", (username, key, salt))
    db.commit()

    return 'User registered successfully', 201

if __name__ == '__main__':
    app.run()