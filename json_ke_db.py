import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from api_dummy import db, DetectorLog, app  # pastikan import dari flask app utama

def import_json_to_db(filename):
    with open(filename, 'r') as f:
        data = json.load(f)

    # pastikan data berupa list
    if isinstance(data, dict):
        data = [data]

    with app.app_context():
        for item in data:
            log = DetectorLog(
                id=item['id'],
                timestamp=datetime.strptime(item['timestamp'], "%Y-%m-%d %H:%M:%S.%f"),
                status=item['status'],
                crossing_duration=item['crossing_duration'],
                total_crossing=item['total_crossing']
            )
            db.session.merge(log)  # merge untuk mencegah duplicate id
        db.session.commit()
        print(f"Berhasil mengimpor {len(data)} data ke database.")

if __name__ == '__main__':
    import_json_to_db('dummy_pedestrian_data.json')
