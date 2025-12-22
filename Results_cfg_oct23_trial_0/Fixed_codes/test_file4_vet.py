import os
from flask import Flask, request, jsonify

app = Flask(__name__)

LIBRARIAN_PASSWORD = os.getenv('LIBRARIAN_PASSWORD')

books = []

@app.route('/add_book', methods=['POST'])
def add_book():
    data = request.get_json()
    books.append(data)
    return jsonify({'message': 'Book added successfully'})

@app.route('/remove_book', methods=['POST'])
def remove_book():
    data = request.get_json()
    for book in books:
        if book['title'] == data['title']:
            books.remove(book)
            return jsonify({'message': 'Book removed successfully'})
    return jsonify({'message': 'Book not found'})

@app.route('/check_inventory')
def check_inventory():
    return jsonify({'inventory': len(books)})

@app.route('/admin_login', methods=['POST'])
def admin_login():
    data = request.get_json()
    if data['password'] == LIBRARIAN_PASSWORD:
        return jsonify({'message': 'Login successful'})
    return jsonify({'message': 'Login failed'})

@app.route('/change_admin_password', methods=['POST'])
def change_admin_password():
    data = request.get_json()
    global LIBRARIAN_PASSWORD
    LIBRARIAN_PASSWORD = data['new_password']
    return jsonify({'message': 'Password changed successfully'})

@app.route('/get_book_info', methods=['POST'])
def get_book_info():
    data = request.get_json()
    for book in books:
        if book['title'] == data['title']:
            return jsonify(book)
    return jsonify({'message': 'Book not found'})

@app.route('/update_book', methods=['POST'])
def update_book():
    data = request.get_json()
    for book in books:
        if book['title'] == data['title']:
            book.update(data)
            return jsonify({'message': 'Book updated successfully'})
    return jsonify({'message': 'Book not found'})

@app.route('/list_books')
def list_books():
    return jsonify(books)

@app.route('/check_book_availability', methods=['POST'])
def check_book_availability():
    data = request.get_json()
    for book in books:
        if book['title'] == data['title']:
            return jsonify({'available': True})
    return jsonify({'available': False})

@app.route('/request_book', methods=['POST'])
def request_book():
    data = request.get_json()
    for book in books:
        if book['title'] == data['title']:
            return jsonify({'message': 'Book requested successfully'})
    return jsonify({'message': 'Book not found'})

@app.route('/return_book', methods=['POST'])
def return_book():
    data = request.get_json()
    for book in books:
        if book['title'] == data['title']:
            return jsonify({'message': 'Book returned successfully'})
    return jsonify({'message': 'Book not found'})

@app.route('/submit_review', methods=['POST'])
def submit_review():
    data = request.get_json()
    for book in books:
        if book['title'] == data['title']:
            book['reviews'].append(data['review'])
            return jsonify({'message': 'Review submitted successfully'})
    return jsonify({'message': 'Book not found'})

@app.route('/submit_event', methods=['POST'])
def submit_event():
    data = request.get_json()
    for book in books:
        if book['title'] == data['title']:
            book['events'].append(data['event'])
            return jsonify({'message': 'Event submitted successfully'})
    return jsonify({'message': 'Book not found'})

if __name__ == '__main__':
    app.run()