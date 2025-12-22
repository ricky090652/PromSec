import os
from flask import Flask, request, jsonify
import yaml
import mysql.connector

app = Flask(__name__)

DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_DATABASE = os.environ.get('DB_DATABASE')

def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_DATABASE
    )

@app.route('/api/temperature_for_location', methods=['POST'])
def get_temperature_for_location():
    data = yaml.safe_load(request.data)
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    date = data.get('date')

    if not latitude or not longitude or not date:
        return jsonify({'error': 'Latitude, longitude, and date are required parameters'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT temperature FROM weather_data WHERE latitude = %s AND longitude = %s AND date = %s"
        cursor.execute(query, (latitude, longitude, date))
        temperature = cursor.fetchone()
        conn.close()
        if temperature:
            return jsonify({'temperature': temperature[0]})
        else:
            return jsonify({'error': 'Temperature data not found for the provided location and date'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/update_weather_data', methods=['POST'])
def update_weather_data():
    location = request.json.get('location')

    if not location:
        return jsonify({'error': 'Location is a required parameter'}), 400

    if ';' in location or '|' in location:
        return jsonify({'error': 'Invalid input'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "UPDATE weather_data SET temperature = %s WHERE location = %s"
        cursor.execute(query, (temperature, location))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Weather data updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run()