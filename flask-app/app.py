from flask import Flask, render_template, jsonify, send_file
import psycopg2
from datetime import datetime, timedelta
import folium
from folium import plugins
import os
import urllib3
import json
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# Initialize urllib3
http = urllib3.PoolManager()

# Database Configuration
DB_CONFIG = {
    'host': 'weather-db.c8dk46wws5y8.us-east-1.rds.amazonaws.com',
    'database': 'weatherdb',
    'user': 'postgres',
    'password': 'Santander1210'
}

CITY_TIMEZONES = {
    'Tokyo': 'Asia/Tokyo',
    'Mumbai': 'Asia/Kolkata', 
    'London': 'Europe/London',
    'Sydney': 'Australia/Sydney',
    'New York': 'America/New_York',
    'Paris': 'Europe/Paris',
    'Dubai': 'Asia/Dubai',
    'Singapore': 'Asia/Singapore',
    'Toronto': 'America/Toronto',
    'São Paulo': 'America/Sao_Paulo',
    'Sao Paulo': 'America/Sao_Paulo'
}

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(**DB_CONFIG)

def get_local_time(city):
    """Get current local time for a city"""
    try:
        # Normalize city name
        city_normalized = city.replace('ÃƒÂ£', 'ã').replace('Ã£', 'ã')
        
        timezone_str = CITY_TIMEZONES.get(city_normalized)
        
        if not timezone_str:
            print(f"No timezone found for city: {city} (normalized: {city_normalized})")
            return "N/A"
        
        local_tz = pytz.timezone(timezone_str)
        utc_now = datetime.now(pytz.utc)
        local_time = utc_now.astimezone(local_tz)
        formatted_time = local_time.strftime('%I:%M %p')
        
        return formatted_time
        
    except Exception as e:
        print(f"ERROR getting time for {city}: {str(e)}")
        import traceback
        traceback.print_exc()
        return "N/A"


def get_latest_weather():
    """Get latest weather data for all cities"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fix duplicate São Paulo by normalizing city names
    query = """
        WITH normalized_cities AS (
            SELECT 
                CASE 
                    WHEN city LIKE '%o Paulo%' THEN 'São Paulo'
                    ELSE city 
                END as normalized_city,
                timestamp,
                temperature_f,
                feels_like,
                humidity,
                pressure,
                wind_speed,
                visibility,
                condition,
                latitude,
                longitude,
                ROW_NUMBER() OVER (
                    PARTITION BY CASE 
                        WHEN city LIKE '%o Paulo%' THEN 'São Paulo'
                        ELSE city 
                    END 
                    ORDER BY timestamp DESC
                ) as rn
            FROM weather_readings
        )
        SELECT 
            normalized_city,
            timestamp,
            temperature_f,
            feels_like,
            humidity,
            pressure,
            wind_speed,
            visibility,
            condition,
            latitude,
            longitude
        FROM normalized_cities
        WHERE rn = 1
        ORDER BY normalized_city
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    data = []
    for row in rows:
        city = row[0]
        timestamp = row[1]
        
        # Get local time for this city
        local_time = get_local_time(city)
        
        data.append({
            'city': city,
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else '',
            'local_time': local_time,  # This is the actual local time
            'temperature': row[2],
            'feels_like': row[3] if row[3] else row[2],
            'humidity': row[4],
            'pressure': row[5] if row[5] else 0,
            'wind_speed': row[6],
            'visibility': row[7] if row[7] else 0,
            'condition': row[8],
            'latitude': row[9] if row[9] else 0,
            'longitude': row[10] if row[10] else 0
        })

    cursor.close()
    conn.close()
    return data

# Routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/latest')
def get_latest_readings():
    """Get latest readings for all cities"""
    try:
        return jsonify(get_latest_weather())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/forecast/<city>')
def get_forecast(city):
    """Proxy to Lambda function for weather forecast - FIXED CORS"""
    try:
        # Normalize city name for São Paulo
        city_normalized = city.replace('ÃƒÂ£', 'ã').replace('Ã£', 'ã')
        
        # Use path parameter format that Lambda expects
        LAMBDA_FORECAST_URL = f'https://ery3vytcl2.execute-api.us-east-1.amazonaws.com/default/weather-forecast-api/{city_normalized}'
        
        print(f"Requesting forecast for {city_normalized} from: {LAMBDA_FORECAST_URL}")
        
        response = http.request('GET', LAMBDA_FORECAST_URL, timeout=15.0)
        
        print(f"Lambda response status: {response.status}")
        
        if response.status != 200:
            error_body = response.data.decode('utf-8') if response.data else 'No error body'
            print(f"Lambda error: {error_body}")
            return jsonify({
                'error': f'Lambda API returned status {response.status}',
                'details': error_body
            }), response.status
        
        data = json.loads(response.data.decode('utf-8'))
        return jsonify(data)
        
    except urllib3.exceptions.TimeoutError:
        return jsonify({'error': 'Request timeout - Lambda did not respond in time'}), 504
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Failed to parse Lambda response: {str(e)}'}), 500
    except Exception as e:
        print(f"Forecast error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/trends/<city>')
def get_city_trends(city):
    """Get 7-day temperature and humidity trends for a city"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Normalize city name
        city_normalized = city.replace('ÃƒÂ£', 'ã').replace('Ã£', 'ã')

        seven_days_ago = datetime.now() - timedelta(days=7)
        query = """
            SELECT
                timestamp,
                temperature_f,
                humidity
            FROM weather_readings
            WHERE (city = %s OR city LIKE %s) AND timestamp > %s
            ORDER BY timestamp ASC
        """
        cursor.execute(query, (city_normalized, f'%{city_normalized.split()[0]}%', seven_days_ago))
        rows = cursor.fetchall()

        data = {
            'labels': [row[0].strftime('%m/%d %H:%M') for row in rows],
            'temperature': [row[1] for row in rows],
            'humidity': [row[2] for row in rows]
        }

        cursor.close()
        conn.close()
        return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts')
def get_active_alerts():
    """Generate simple weather alerts"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            WITH normalized_cities AS (
                SELECT 
                    CASE 
                        WHEN city LIKE '%o Paulo%' THEN 'São Paulo'
                        ELSE city 
                    END as normalized_city,
                    temperature_f,
                    wind_speed,
                    ROW_NUMBER() OVER (
                        PARTITION BY CASE 
                            WHEN city LIKE '%o Paulo%' THEN 'São Paulo'
                            ELSE city 
                        END 
                        ORDER BY timestamp DESC
                    ) as rn
                FROM weather_readings
            )
            SELECT normalized_city, temperature_f, wind_speed
            FROM normalized_cities
            WHERE rn = 1
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        alerts = []
        for city, temp, wind in rows:
            if temp > 95:
                alerts.append({'type': 'heat', 'city': city, 'message': f'🔥 Heat Alert: {temp}°F'})
            if temp < 20:
                alerts.append({'type': 'cold', 'city': city, 'message': f'❄️ Cold Alert: {temp}°F'})
            if wind > 50:
                alerts.append({'type': 'wind', 'city': city, 'message': f'💨 High Wind Alert: {wind} mph'})

        cursor.close()
        conn.close()
        return jsonify(alerts)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

WEATHER_ICONS = {
    'clear sky': '☀️',
    'few clouds': '🌤️',
    'scattered clouds': '⛅',
    'broken clouds': '☁️',
    'overcast clouds': '☁️',
    'shower rain': '🌧️',
    'rain': '🌧️',
    'light rain': '🌦️',
    'thunderstorm': '⛈️',
    'snow': '❄️',
    'mist': '🌫️',
    'fog': '🌫️',
    'haze': '🌫️'
}

def get_weather_icon(condition):
    """Return emoji icon for weather condition"""
    return WEATHER_ICONS.get(condition.lower(), '🌡️')

@app.route('/api/map')
def get_weather_map():
    """Generate and serve the Folium weather map"""
    try:
        weather_data = get_latest_weather()

        m = folium.Map(
            location=[20, 0],
            zoom_start=2,
            tiles='cartodbpositron',
            max_bounds=True
        )

        for city_data in weather_data:
            city = city_data['city']
            lat, lon = city_data['latitude'], city_data['longitude']
            
            if not lat or not lon or lat == 0 or lon == 0:
                print(f"Skipping {city} - no coordinates")
                continue

            temp = round(city_data['temperature'])
            condition = city_data['condition']
            humidity = city_data['humidity']
            wind_speed = city_data['wind_speed']
            feels_like = round(city_data['feels_like'])
            pressure = city_data['pressure']
            icon_emoji = get_weather_icon(condition)

            popup_html = f"""
            <div style="font-family: 'Inter', Arial, sans-serif; min-width: 200px;">
                <h3 style="margin: 0 0 10px 0; font-size: 1.3em; color: #1d1d1f;">
                    {icon_emoji} {city}
                </h3>
                <div style="font-size: 2.5em; font-weight: 300; margin: 10px 0; color: #0071e3;">
                    {temp}°F
                </div>
                <div style="color: #86868b; margin-bottom: 12px; text-transform: capitalize;">
                    {condition}
                </div>
                <div style="border-top: 1px solid #e5e5e7; padding-top: 10px; font-size: 0.9em;">
                    <div><strong>Feels like:</strong> {feels_like}°F</div>
                    <div><strong>Humidity:</strong> {humidity}%</div>
                    <div><strong>Wind:</strong> {wind_speed} mph</div>
                    <div><strong>Pressure:</strong> {pressure}</div>
                </div>
            </div>
            """

            icon_html = f'<div style="font-size: 32px; text-align: center;">{icon_emoji}</div>'
            icon = folium.DivIcon(html=icon_html)

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{city}: {temp}°F",
                icon=icon
            ).add_to(m)

        plugins.Fullscreen(
            position='topright',
            title='Fullscreen',
            title_cancel='Exit fullscreen',
            force_separate_button=True
        ).add_to(m)

        os.makedirs('static', exist_ok=True)
        map_path = 'static/weather_map.html'
        m.save(map_path)

        return send_file(map_path, mimetype='text/html')

    except Exception as e:
        print(f"Map error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
