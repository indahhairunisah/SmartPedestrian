from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api, reqparse, fields, marshal_with, abort
# from people_detector import generate_stream  # Assuming this is a custom module for video streaming
from data_Penjalan import start_mqtt, latest_data   # Assuming this is a custom module for MQTT
# import detector_threading
import threading
import cv2
from datetime import datetime, date, timedelta
from cek_log import get_all_logs  # Assuming this is a custom module for database operations
from weather import get_weather_data
from sqlalchemy import func, and_, desc
import json

app = Flask(__name__)
app.secret_key = 'rahasia123'  # untuk session login
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
api = Api(app)

# ====================== MODEL ======================
class UserModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f"User(name={self.name}, email={self.email})"

#======================== DB log ==========================
class DetectorLog(db.Model):
    __tablename__ = 'detector_log'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(10))  # "WALK" atau "STOP"
    crossing_duration = db.Column(db.Float)
    total_crossing = db.Column(db.Integer)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'crossing_duration': self.crossing_duration,
            'total_crossing': self.total_crossing
        }

def save_log(status, crossing_duration, total_crossing):
    try:
        log = DetectorLog(
            status=status,
            crossing_duration=crossing_duration,
            total_crossing=total_crossing
        )
        db.session.add(log)
        db.session.commit()
        print(f"✅ Log saved: {status}, duration: {crossing_duration}, crossing: {total_crossing}")
        return True
    except Exception as e:
        print(f"❌ Error saving log: {str(e)}")
        db.session.rollback()
        return False

# ====================== PARSER ======================
user_args = reqparse.RequestParser()
user_args.add_argument('name', type=str, required=True, help="Name cannot be blank!")
user_args.add_argument('email', type=str, required=True, help="Email cannot be blank!")

userFields = {
    'id': fields.Integer,
    'name': fields.String,
    'email': fields.String
}

# ====================== API RESOURCES ======================
class Users(Resource):
    @marshal_with(userFields)
    def get(self):
        users = UserModel.query.all()
        return users

    @marshal_with(userFields)
    def post(self):
        args = user_args.parse_args()
        user = UserModel(name=args["name"], email=args["email"])
        db.session.add(user)
        db.session.commit()
        return UserModel.query.all(), 201

class User(Resource):
    @marshal_with(userFields)
    def get(self, id):
        user = UserModel.query.filter_by(id=id).first()
        if not user:
            abort(404, "User Not Found")
        return user

    @marshal_with(userFields)
    def patch(self, id):
        args = user_args.parse_args()
        user = UserModel.query.filter_by(id=id).first()
        if not user:
            abort(404, "User Not Found")
        user.name = args["name"]
        user.email = args["email"]
        db.session.commit()
        return user

    @marshal_with(userFields)
    def delete(self, id):
        user = UserModel.query.filter_by(id=id).first()
        if not user:
            abort(404, "User Not Found")
        db.session.delete(user)
        db.session.commit()
        return UserModel.query.all(), 200

api.add_resource(Users, '/api/users/')
api.add_resource(User, '/api/users/<int:id>')

# ====================== DUMMY LOGIN (HARDCODED) ======================
USER = {
    "username": "admin",
    "password": "admin123"
}

# ====================== DATABASE INITIALIZATION ======================
def init_database():
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database dan tabel berhasil dibuat!")
            
            # Create some sample data if table is empty
            if DetectorLog.query.count() == 0:
                print("📝 Creating sample data...")
                sample_data = [
                    DetectorLog(timestamp=datetime.now() - timedelta(hours=i), 
                               status='WALK' if i % 2 == 0 else 'STOP',
                               crossing_duration=25.5 + (i * 2.3),
                               total_crossing=5 + (i % 10))
                    for i in range(24)  # 24 hours of sample data
                ]
                
                for log in sample_data:
                    db.session.add(log)
                
                db.session.commit()
                print("✅ Sample data created!")
                
        except Exception as e:
            print(f"❌ Database initialization error: {str(e)}")

# Initialize database
init_database()

# ====================== ROUTING WEB ======================
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        if uname == USER['username'] and pwd == USER['password']:
            session['user'] = uname
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Username atau password salah")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        weather = get_weather_data()
    except Exception as e:
        print(f"❌ Error getting weather data: {str(e)}")
        # Fallback weather data
        weather = {
            'weather_desc': 'Cerah',
            'temperature': '28',
            'humidity': '65',
            'windspeed': '12'
        }
    
    return render_template('dashboard.html', weather=weather)

@app.route('/api/weather')
def api_weather():
    try:
        weather = get_weather_data()
        return jsonify({'success': True, 'weather': weather})
    except Exception as e:
        print(f"❌ Weather API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'weather': {
                'weather_desc': 'Data tidak tersedia',
                'temperature': '--',
                'humidity': '--',
                'windspeed': '--'
            }
        })

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

#======================= STREAMING VIDEO ======================
@app.route('/detect')
def detect():
    return render_template('running.html')

#========================= status awal ========================


@app.route("/status")
def status():
    return render_template("status.html")

# Halaman utama
@app.route('/halaman_utama')
def halaman_utama():
    return render_template('halaman_utama.html')

@app.route('/dashboard_cam2')
def dashboard_cam2():
    return render_template('dashboard_cam2.html')

@app.route('/dashboard_cam3')
def dashboard_cam3():
    return render_template('dashboard_cam3.html')


@app.route('/dashboard_cam4')
def dashboard_cam4():
    return render_template('dashboard_cam4.html')

@app.route('/system_info')
def system_info():
    return render_template('system_info.html')

# Initialize MQTT
try:
    start_mqtt()
    print("✅ MQTT started successfully")
except Exception as e:
    print(f"❌ MQTT initialization error: {str(e)}")
last_status = "STOP"
@app.route('/get_status')
def get_status():
    global last_status
    # try:
    current_status = latest_data.get("status")
    count_middle = latest_data.get("count_middle")
    crossing_duration = latest_data.get("crossing_duration")
    waktu_crossing = latest_data.get("waktu_crossing")
    total_crossing = latest_data.get("total_crossing")
    print("data:" ,latest_data.get("status"))
    # Save log when status changes and there's meaningful data
    if last_status != current_status:
        print("save_data")
        if ( latest_data.get("status") != "WALK" and int(crossing_duration) > 0 and 
            total_crossing > 0):
            
            if save_log(current_status, crossing_duration, total_crossing):
                print(f"✅ Log saved: {current_status}, duration: {crossing_duration}, crossing: {total_crossing}")
        
        last_status = current_status
    
    return jsonify({
        "success": True,
        "status": current_status,
        "count_middle": count_middle,
        "crossing_duration": int(waktu_crossing),
        "total_crossing": total_crossing
    })
        
    # except Exception as e:
    #     print(f"❌ Error in get_status: {str(e)}")
    #     return jsonify({
    #         "success": False,
    #         "error": str(e),
    #         "status": "STOP",
    #         "count_middle": 0,
    #         "crossing_duration": 0,
    #         "total_crossing": 0
    #     })

#======================== ambil data log ===========================
@app.route("/today_crossing")
def today_crossing():
    try:
        today = date.today()
        
        # Filter log hanya untuk hari ini
        logs_today = DetectorLog.query.filter(
            func.date(DetectorLog.timestamp) == today
        ).all()
        
        # Ambil total crossing dari semua log hari ini
        total_crossings = sum(log.total_crossing or 0 for log in logs_today)
        
        return jsonify({
            "success": True,
            "date": today.isoformat(),
            "total_crossing_today": total_crossings,
            "total_records": len(logs_today)
        })
        
    except Exception as e:
        print(f"❌ Error in today_crossing: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "total_crossing_today": 0
        })

@app.route("/Tcrossing_day")
def Tcrossing_day():
    try:
        today = date.today()
        
        # Filter log hanya untuk hari ini
        logs_today = DetectorLog.query.filter(
            func.date(DetectorLog.timestamp) == today
        ).all()
        
        # Hitung rata-rata crossing_duration (yang bukan None)
        durations = [log.crossing_duration for log in logs_today if log.crossing_duration is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return jsonify({
            "success": True,
            "date": today.isoformat(),
            "average_crossing_duration": round(avg_duration, 2),
            "total_records": len(durations)
        })
        
    except Exception as e:
        print(f"❌ Error in Tcrossing_day: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "average_crossing_duration": 0
        })

@app.route("/jamSibuk")
def jamSibuk():
    try:
        today = date.today()
        
        # Filter log hanya untuk hari ini
        logs_today = DetectorLog.query.filter(
            func.date(DetectorLog.timestamp) == today
        ).all()
        
        # Kelompokkan crossing per jam
        hour_counts = {}
        for log in logs_today:
            if log.timestamp and log.total_crossing:
                hour = log.timestamp.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + (log.total_crossing or 0)

        # Cari jam dengan crossing terbanyak
        if hour_counts:
            busiest_hour = max(hour_counts, key=hour_counts.get)
            max_crossing = hour_counts[busiest_hour]
            busiest_hour_str = f"{busiest_hour:02d}:00 - {busiest_hour:02d}:59"
        else:
            busiest_hour_str = "Tidak ada data"
            max_crossing = 0

        return jsonify({
            "success": True,
            "date": today.isoformat(),
            "busiest_hour": busiest_hour_str,
            "total_crossing": max_crossing,
            "hour_data": hour_counts
        })
        
    except Exception as e:
        print(f"❌ Error in jamSibuk: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "busiest_hour": "Error"
        })

# ============= GRAFIK DINAMIS =================
@app.route('/api/grafik-periode')
def grafik_periode():
    try:
        mode = request.args.get('mode', 'today')
        start = request.args.get('start')
        end = request.args.get('end')

        print(f"📊 Grafik request: mode={mode}, start={start}, end={end}")

        now = datetime.now()
        
        # Tentukan rentang waktu berdasarkan mode
        if mode == 'today':
            start_date = datetime(now.year, now.month, now.day)
            end_date = start_date + timedelta(days=1)
            group_format = '%H'
            
        elif mode == 'week':
            # Mulai dari hari Senin minggu ini
            start_date = now - timedelta(days=now.weekday())
            start_date = datetime(start_date.year, start_date.month, start_date.day)
            end_date = start_date + timedelta(days=7)
            group_format = '%Y-%m-%d'
            
        elif mode == 'month':
            start_date = datetime(now.year, now.month, 1)
            if now.month == 12:
                end_date = datetime(now.year + 1, 1, 1)
            else:
                end_date = datetime(now.year, now.month + 1, 1)
            group_format = '%Y-%m-%d'
            
        elif mode == 'custom' and start and end:
            start_date = datetime.strptime(start, '%Y-%m-%d')
            end_date = datetime.strptime(end, '%Y-%m-%d') + timedelta(days=1)
            
            # Tentukan format berdasarkan rentang waktu
            diff_days = (end_date - start_date).days
            if diff_days <= 1:
                group_format = '%H'
            elif diff_days <= 31:
                group_format = '%Y-%m-%d'
            else:
                group_format = '%Y-%m'
        else:
            return jsonify({
                "success": False,
                "error": "Invalid parameters",
                "message": f"Mode: {mode}, Start: {start}, End: {end}"
            }), 400

        print(f"📅 Date range: {start_date} to {end_date}")

        # Query data dari database
        if mode == 'today':
            # Untuk hari ini, group by jam
            result = (
                db.session.query(
                    func.strftime('%H', DetectorLog.timestamp).label('periode'),
                    func.sum(DetectorLog.total_crossing).label('total_crossing'),
                    func.avg(DetectorLog.crossing_duration).label('avg_duration'),
                    func.count(DetectorLog.id).label('frequency')
                )
                .filter(
                    DetectorLog.timestamp >= start_date,
                    DetectorLog.timestamp < end_date,
                    DetectorLog.total_crossing.isnot(None)
                )
                .group_by(func.strftime('%H', DetectorLog.timestamp))
                .order_by('periode')
                .all()
            )
            
        else:
            # Untuk week, month, dan custom
            result = (
                db.session.query(
                    func.strftime(group_format, DetectorLog.timestamp).label('periode'),
                    func.sum(DetectorLog.total_crossing).label('total_crossing'),
                    func.avg(DetectorLog.crossing_duration).label('avg_duration'),
                    func.count(DetectorLog.id).label('frequency')
                )
                .filter(
                    DetectorLog.timestamp >= start_date,
                    DetectorLog.timestamp < end_date,
                    DetectorLog.total_crossing.isnot(None)
                )
                .group_by(func.strftime(group_format, DetectorLog.timestamp))
                .order_by('periode')
                .all()
            )

        print(f"📈 Query result count: {len(result)}")

        # Format data untuk response
        labels = []
        data_crossings = []
        data_durations = []
        
        for row in result:
            periode = row.periode
            total_crossing = int(row.total_crossing or 0)
            avg_duration = round(float(row.avg_duration or 0), 2)
            
            # Format label berdasarkan mode
            if mode == 'today':
                labels.append(f"{periode}:00")
            elif mode == 'week':
                # Convert date to day name
                try:
                    date_obj = datetime.strptime(periode, '%Y-%m-%d')
                    day_names = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
                    labels.append(day_names[date_obj.weekday()])
                except:
                    labels.append(periode)
            else:
                labels.append(periode)
                
            data_crossings.append(total_crossing)
            data_durations.append(avg_duration)

        # Cari jam/periode sibuk
        max_crossing = max(data_crossings) if data_crossings else 0
        jam_sibuk = None
        if max_crossing > 0:
            max_index = data_crossings.index(max_crossing)
            jam_sibuk = labels[max_index] if max_index < len(labels) else None

        response_data = {
            "success": True,
            "mode": mode,
            "labels": labels,
            "data_crossings": data_crossings,
            "data_durations": data_durations,
            "jam_sibuk": jam_sibuk,
            "total_records": len(result),
            "period_start": start_date.strftime('%Y-%m-%d %H:%M:%S'),
            "period_end": end_date.strftime('%Y-%m-%d %H:%M:%S'),
            "max_crossing": max_crossing
        }

        print(f"✅ Grafik response: {len(labels)} data points, max crossing: {max_crossing}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ Error in grafik_periode: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": "Database error",
            "message": str(e),
            "labels": [],
            "data_crossings": [],
            "data_durations": []
        }), 500

# Endpoint tambahan untuk mendapatkan detail periode tertentu
@app.route('/api/detail-periode')
def detail_periode():
    try:
        mode = request.args.get('mode', 'today')
        periode = request.args.get('periode')
        
        print(f"🔍 Detail request: mode={mode}, periode={periode}")
        
        if not periode:
            return jsonify({
                "success": False,
                "error": "Periode parameter required"
            }), 400
        
        now = datetime.now()
        
        if mode == 'today':
            # Parse jam (format: "14:00")
            try:
                hour = int(periode.split(':')[0])
                start_time = datetime(now.year, now.month, now.day, hour)
                end_time = start_time + timedelta(hours=1)
            except:
                return jsonify({
                    "success": False,
                    "error": "Invalid time format"
                }), 400
            
        elif mode == 'week' or mode == 'month':
            # Parse tanggal atau nama hari
            try:
                if periode in ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']:
                    # Convert day name to date
                    day_names = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
                    day_index = day_names.index(periode)
                    start_of_week = now - timedelta(days=now.weekday())
                    target_date = start_of_week + timedelta(days=day_index)
                    start_time = datetime(target_date.year, target_date.month, target_date.day)
                else:
                    date_obj = datetime.strptime(periode, '%Y-%m-%d')
                    start_time = datetime(date_obj.year, date_obj.month, date_obj.day)
                end_time = start_time + timedelta(days=1)
            except:
                return jsonify({
                    "success": False,
                    "error": "Invalid date format"
                }), 400
            
        else:
            return jsonify({
                "success": False,
                "error": "Invalid mode"
            }), 400
            
        # Query detail data
        logs = DetectorLog.query.filter(
            DetectorLog.timestamp >= start_time,
            DetectorLog.timestamp < end_time,
            DetectorLog.total_crossing.isnot(None)
        ).order_by(DetectorLog.timestamp.desc()).all()
        
        # Hitung statistik
        total_crossings = sum(log.total_crossing or 0 for log in logs)
        durations = [log.crossing_duration for log in logs if log.crossing_duration is not None]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0
        
        # Format response
        detail_logs = []
        for log in logs[:10]:  # Ambil 10 record terakhir
            detail_logs.append({
                "id": log.id,
                "timestamp": log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else None,
                "status": log.status,
                "crossing_duration": log.crossing_duration,
                "total_crossing": log.total_crossing
            })
        
        response_data = {
            "success": True,
            "periode": periode,
            "total_crossings": total_crossings,
            "avg_duration": avg_duration,
            "total_records": len(logs),
            "detail_logs": detail_logs,
            "period_start": start_time.strftime('%Y-%m-%d %H:%M:%S'),
            "period_end": end_time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"✅ Detail response: {total_crossings} crossings, {len(logs)} records")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ Error in detail_periode: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": "Database error", 
            "message": str(e)
        }), 500

# ============= ADDITIONAL API ENDPOINTS =================
@app.route('/api/logs')
def get_logs():
    """Get all logs with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        logs = DetectorLog.query.order_by(DetectorLog.timestamp.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            "success": True,
            "logs": [log.to_dict() for log in logs.items],
            "total": logs.total,
            "pages": logs.pages,
            "current_page": page,
            "per_page": per_page
        })
        
    except Exception as e:
        print(f"❌ Error in get_logs: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/stats')
def get_stats():
    """Get overall statistics"""
    try:
        today = date.today()
        
        # Today's stats
        today_logs = DetectorLog.query.filter(
            func.date(DetectorLog.timestamp) == today
        ).all()
        
        # All time stats
        all_logs = DetectorLog.query.all()
        
        stats = {
            "today": {
                "total_crossings": sum(log.total_crossing or 0 for log in today_logs),
                "total_records": len(today_logs),
                "avg_duration": round(
                    sum(log.crossing_duration or 0 for log in today_logs) / len(today_logs), 2
                ) if today_logs else 0
            },
            "all_time": {
                "total_crossings": sum(log.total_crossing or 0 for log in all_logs),
                "total_records": len(all_logs),
                "avg_duration": round(
                    sum(log.crossing_duration or 0 for log in all_logs) / len(all_logs), 2
                ) if all_logs else 0
            }
        }
        
        return jsonify({
            "success": True,
            "stats": stats
        })
        
    except Exception as e:
        print(f"❌ Error in get_stats: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ============= ERROR HANDLERS =================
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint not found",
        "message": "The requested URL was not found on the server."
    }), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({
        "success": False,
        "error": "Internal server error",
        "message": "An internal server error occurred."
    }), 500

# ============= HEALTH CHECK =================
@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        
        # Get basic stats
        total_logs = DetectorLog.query.count()
        
        return jsonify({
            "success": True,
            "status": "healthy",
            "database": "connected",
            "total_logs": total_logs,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# ====================== RUN APP ======================
if __name__ == '__main__':
    print("🚀 Starting Smart Pedestrian Crossing API...")
    print("📊 Dashboard available at: http://localhost:5000/dashboard")
    print("🔧 API endpoints:")
    print("   - GET /api/grafik-periode")
    print("   - GET /api/detail-periode")
    print("   - GET /api/weather")
    print("   - GET /api/health")
    print("   - GET /api/stats")
    print("   - GET /api/logs")
    
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)