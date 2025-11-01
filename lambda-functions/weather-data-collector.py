import json
import boto3
import os
import urllib3
from datetime import datetime
import psycopg2

s3_client = boto3.client('s3')
sns_client = boto3.client('sns')
http = urllib3.PoolManager()

API_KEY = os.environ['OPENWEATHER_API_KEY']
DB_HOST = os.environ['DB_HOST']
DB_NAME = os.environ['DB_NAME']
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
S3_BUCKET = os.environ['S3_BUCKET']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

CITIES = [
    'Tokyo',
    'Mumbai', 
    'London',
    'Sydney',
    'New York',
    'Paris',
    'Dubai',
    'Singapore',
    'Toronto',
    'Sao Paulo'
]

def lambda_handler(event, context):
    print("Starting weather data collection for 10 cities...")
    results = []
    alerts = []
    
    for city in CITIES:
        try:
            weather_data = fetch_weather(city.strip())
            
            if weather_data:
                store_raw_data_s3(city.strip(), weather_data)
                processed = process_weather_data(weather_data)
                store_in_rds(processed)
                
                alert = check_alerts(processed)
                if alert:
                    alerts.extend(alert)
                
                results.append({
                    'city': city.strip(),
                    'status': 'success',
                    'temperature': processed['temperature_f']
                })
            
        except Exception as e:
            print(f"Error processing {city}: {str(e)}")
            results.append({
                'city': city.strip(),
                'status': 'error',
                'error': str(e)
            })
    
    if alerts:
        send_alerts(alerts)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Weather data collection completed for {len(CITIES)} cities',
            'results': results,
            'alerts': len(alerts)
        })
    }

def fetch_weather(city):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=imperial"
    response = http.request("GET", url, timeout=urllib3.Timeout(connect=5.0, read=10.0))
    
    if response.status == 200:
        return json.loads(response.data.decode('utf-8'))
    else:
        print(f"API Error for {city}: {response.status}")
        return None

def store_raw_data_s3(city, data):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    key = f"raw-weather-data/{city}/{timestamp}.json"
    
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data),
        ContentType='application/json'
    )
    print(f"Stored raw data in S3: {key}")

def process_weather_data(data):
    return {
        'city': data['name'],
        'timestamp': datetime.now(),
        'temperature_f': round(data['main']['temp'], 2),
        'feels_like': round(data['main']['feels_like'], 2),
        'humidity': data['main']['humidity'],
        'pressure': data['main']['pressure'],
        'wind_speed': round(data['wind']['speed'], 2),
        'visibility': data.get('visibility', 0),
        'condition': data['weather'][0]['description'],
        'latitude': data['coord']['lat'],
        'longitude': data['coord']['lon']
    }

def store_in_rds(data):
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_readings (
                id SERIAL PRIMARY KEY,
                city VARCHAR(100) NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                temperature_f FLOAT,
                feels_like FLOAT,
                humidity FLOAT,
                pressure FLOAT,
                wind_speed FLOAT,
                visibility FLOAT,
                condition VARCHAR(200),
                latitude FLOAT,
                longitude FLOAT,
                CONSTRAINT unique_city_timestamp UNIQUE(city, timestamp)
            )
        """)
        
        cursor.execute("""
            INSERT INTO weather_readings 
            (city, timestamp, temperature_f, feels_like, humidity, pressure, 
             wind_speed, visibility, condition, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (city, timestamp) DO NOTHING
        """, (
            data['city'],
            data['timestamp'],
            data['temperature_f'],
            data['feels_like'],
            data['humidity'],
            data['pressure'],
            data['wind_speed'],
            data['visibility'],
            data['condition'],
            data['latitude'],
            data['longitude']
        ))
        
        conn.commit()
        print(f"Stored data in RDS for {data['city']}")
        
    except Exception as e:
        print(f"Database error: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def check_alerts(data):
    alerts = []
    
    if data['temperature_f'] > 95:
        alerts.append(f"🔥 HEAT ALERT: {data['city']} - {data['temperature_f']}°F")
    
    if data['temperature_f'] < 20:
        alerts.append(f"❄️ COLD ALERT: {data['city']} - {data['temperature_f']}°F")
    
    if data['wind_speed'] > 50:
        alerts.append(f"💨 HIGH WIND ALERT: {data['city']} - {data['wind_speed']} mph")
    
    return alerts if alerts else None

def send_alerts(alerts):
    message = "⚠️ WEATHER ALERTS ⚠️\n\n" + "\n".join(alerts)
    
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject='Weather Alert Notification',
            Message=message
        )
        print(f"Sent {len(alerts)} alerts via SNS")
    except Exception as e:
        print(f"Error sending SNS alerts: {str(e)}")