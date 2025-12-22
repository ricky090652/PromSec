import os
import hashlib
import random
from flask import Flask, request, redirect

app = Flask(__name__)

def generate_salt():
    return os.urandom(16)

def hash_password(password, salt):
    return hashlib.sha256(password.encode() + salt).hexdigest()

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    
    salt = generate_salt()
    hashed_password = hash_password(password, salt)
    
    # Connect to MySQL database
    # Assume the connection is established
    
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    
    if user:
        return redirect('/login', code=307)
    else:
        cursor.execute("INSERT INTO users (username, password, salt) VALUES (%s, %s, %s)", (username, hashed_password, salt))
        connection.commit()
        return "Registration successful"

if __name__ == '__main__':
    app.run(debug=False)