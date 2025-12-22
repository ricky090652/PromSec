import os
from flask import Flask, request, jsonify

app = Flask(__name__)

LIBRARIAN_PASSWORD = os.getenv('LIBRARIAN_PASSWORD')

@app.route('/add_book', methods=['POST'])
def add_book():
    data = request.get_json()
    title = data.get('title')
    author = data.get('author')
    isbn = data.get('isbn')
    
    # Add book to database
    
    response = {
        'status': 'success',
        'title': title
    }
    
    return jsonify(response)

@app.route('/run_inventory', methods=['GET'])
def run_inventory():
    section = request.args.get('section')
    
    # Execute inventory_script.py with section as argument
    
    response = {
        'message': 'Inventory check initiated for section: {}'.format(section)
    }
    
    return jsonify(response)

@app.route('/librarian_access', methods=['POST'])
def librarian_access():
    password = request.form.get('password')
    
    if password == LIBRARIAN_PASSWORD:
        response = {
            'message': 'Librarian access granted'
        }
        return jsonify(response)
    else:
        return jsonify({'message': 'Access denied'}), 401

if __name__ == '__main__':
    app.run()