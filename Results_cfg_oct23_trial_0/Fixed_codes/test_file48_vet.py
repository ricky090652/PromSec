import os
from flask import Flask, request
import mysql.connector
import hashlib

app = Flask(__name__)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_user = os.environ.get('DB_USER', 'root')
    db_passwd = os.environ.get('DB_PASSWD', 'root')
    db_db = os.environ.get('DB_DB', 'db')
    
    db = mysql.connector.connect(
        host=db_host,
        user=db_user,
        passwd=db_passwd,
        db=db_db
    )
    
    cursor = db.cursor()
    
    query = "SELECT * FROM userdaten WHERE username = %s AND passwort = MD5(%s)"
    cursor.execute(query, (username, password))
    
    result = cursor.fetchone()
    
    if result:
        return "Eingeloggt"
    else:
        return "Falscher Benutzername oder Passwort"

if __name__ == '__main__':
    app.run()