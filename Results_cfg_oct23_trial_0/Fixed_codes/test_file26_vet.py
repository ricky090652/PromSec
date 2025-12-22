import os
from flask import Flask, request, jsonify

app = Flask(__name__)

admin_password = os.getenv('ADMIN_PASSWORD')
database = []

def is_admin(password):
    return password == admin_password

def add_book(title, author):
    database.append({'title': title, 'author': author})

def execute_inventory():
    return jsonify(database)

@app.route('/add_book', methods=['POST'])
def add_new_book():
    data = request.get_json()
    title = data.get('title')
    author = data.get('author')
    
    add_book(title, author)
    
    return 'Book added successfully'

@app.route('/inventory', methods=['GET'])
def get_inventory():
    return execute_inventory()

@app.route('/grant_admin', methods=['POST'])
def grant_admin_access():
    data = request.get_json()
    password = data.get('password')
    
    if is_admin(password):
        return 'Admin access granted'
    else:
        return 'Incorrect password'

if __name__ == '__main__':
    app.run()