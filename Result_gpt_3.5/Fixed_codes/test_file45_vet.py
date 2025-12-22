import os
from flask import Flask, request, redirect, session
from flask_mysqldb import MySQL

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')

app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB')

mysql = MySQL(app)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
    user = cur.fetchone()
    cur.close()

    if user:
        session['user_id'] = user['id']
        session['role'] = user['role']
        return redirect('/dashboard')
    else:
        return redirect('/login')

if __name__ == '__main__':
    app.run()