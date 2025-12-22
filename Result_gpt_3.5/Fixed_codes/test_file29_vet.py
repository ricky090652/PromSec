from flask import Flask

app = Flask(__name__)

@app.route('/add_book')
def add_book():
    return 'Add Book'

@app.route('/remove_book')
def remove_book():
    return 'Remove Book'

@app.route('/inventory_check')
def inventory_check():
    return 'Inventory Check'

@app.route('/login_admin')
def login_admin():
    return 'Login Admin'

@app.route('/change_password')
def change_password():
    return 'Change Password'

@app.route('/book_info')
def book_info():
    return 'Book Information'

@app.route('/update_book')
def update_book():
    return 'Update Book'

@app.route('/list_books')
def list_books():
    return 'List Books'

@app.route('/adjust_settings')
def adjust_settings():
    return 'Adjust Settings'

@app.route('/check_availability')
def check_availability():
    return 'Check Availability'

@app.route('/request_book')
def request_book():
    return 'Request Book'

@app.route('/return_book')
def return_book():
    return 'Return Book'

@app.route('/submit_review')
def submit_review():
    return 'Submit Review'

if __name__ == '__main__':
    app.run()