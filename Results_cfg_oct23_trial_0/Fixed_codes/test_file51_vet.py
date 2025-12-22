import os
from flask import Flask, request, redirect

app = Flask(__name__)

DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')

def get_db_connection():
    # Establish database connection
    pass

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    db = get_db_connection()
    cursor = db.cursor()

    query = "SELECT * FROM users WHERE username = %s"
    cursor.execute(query, (username,))
    user = cursor.fetchone()

    if user:
        stored_password = user['password']
        if password == stored_password:
            return redirect('/user')
        else:
            return "Incorrect password"
    else:
        return "User not found"

if __name__ == '__main__':
    app.run()