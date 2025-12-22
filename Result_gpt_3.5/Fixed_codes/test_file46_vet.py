import os
from flask import Flask, request
import mysql.connector
import hashlib

app = Flask(__name__)

db_host = os.environ.get('DB_HOST', 'localhost')
db_user = os.environ.get('DB_USER', 'root')
db_passwd = os.environ.get('DB_PASSWD', 'root')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_login(username, password):
    hashed_password = hash_password(password)
    
    conn = mysql.connector.connect(host=db_host, user=db_user, passwd=db_passwd, database='db')
    cursor = conn.cursor()
    
    query = "SELECT * FROM user WHERE username = %s AND password = %s"
    cursor.execute(query, (username, hashed_password))
    
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if result:
        return "Good Login"
    else:
        return "Bad Login"

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    result = check_login(username, password)
    
    return result

if __name__ == '__main__':
    app.run()