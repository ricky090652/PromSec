import os
from flask import Flask, request, redirect
import mysql.connector

app = Flask(__name__)

db_host = os.environ.get('DB_HOST', 'localhost')
db_user = os.environ.get('DB_USER', 'root')
db_passwd = os.environ.get('DB_PASSWD', 'root')
db_db = os.environ.get('DB_DB', 'db')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    conn = mysql.connector.connect(host=db_host, user=db_user, passwd=db_passwd, db=db_db)
    cursor = conn.cursor()

    query = "SELECT * FROM users WHERE username = %s AND password = %s"
    cursor.execute(query, (username, password))
    result = cursor.fetchall()

    if result:
        return redirect('/dashboard')
    else:
        return redirect('/')

if __name__ == '__main__':
    app.run()