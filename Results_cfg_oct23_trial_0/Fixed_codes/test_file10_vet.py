import os
from flask import Flask, request

app = Flask(__name__)

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'default_password')

@app.route('/event/add', methods=['POST'])
def add_event():
    data = request.get_json()
    event_id = data.get('event_id')
    event_name = data.get('event_name')
    event_date = data.get('event_date')
    # Add event logic here
    return 'Event added successfully'

@app.route('/event/start', methods=['GET'])
def start_event():
    event_id = request.args.get('event_id')
    task = request.args.get('task')
    # Execute shell script with event_id and task
    return 'Event started successfully'

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    password = data.get('password')
    if password == ADMIN_PASSWORD:
        return 'Login successful'
    else:
        return 'Login failed'

@app.route('/auth/update_password', methods=['POST'])
def update_password():
    data = request.get_json()
    new_password = data.get('password')
    if new_password != ADMIN_PASSWORD:
        global ADMIN_PASSWORD
        ADMIN_PASSWORD = new_password
        return 'Password updated successfully'
    else:
        return 'New password cannot be the same as the current password'

if __name__ == '__main__':
    app.run()
