import json
import os
import urllib3
import psycopg2
from urllib.parse import urlencode, unquote

DB_CONFIG = {
    'host': 'weather-db.c8dk46wws5y8.us-east-1.rds.amazonaws.com',
    'database': 'weatherdb',
    'user': 'postgres',
    'password': 'Santander1210'
}

OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY')
OPENWEATHER_FORECAST_URL = 'https://api.openweathermap.org/data/2.5/forecast'

http = urllib3.PoolManager()

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(**DB_CONFIG)

def normalize_city_name(city):
    """Normalize city names to handle encoding issues"""
    if not city:
        return None
    
    city = city.replace('ÃƒÂ£', 'ã').replace('Ã£', 'ã')
    
    city = unquote(city)
    
    return city

def get_city_coordinates(city_name):
    """Get coordinates for a city from database with fallback"""
    
    FALLBACK_COORDINATES = {
        'Tokyo': (35.6762, 139.6503),
        'Mumbai': (19.0760, 72.8777),
        'London': (51.5074, -0.1278),
        'Sydney': (-33.8688, 151.2093),
        'New York': (40.7128, -74.0060),
        'Paris': (48.8566, 2.3522),
        'Dubai': (25.2048, 55.2708),
        'Singapore': (1.3521, 103.8198),
        'Toronto': (43.6532, -79.3832),
        'São Paulo': (-23.5505, -46.6333),
        'Sao Paulo': (-23.5505, -46.6333)
    }
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    city_normalized = normalize_city_name(city_name)
    
    query = """
        SELECT DISTINCT latitude, longitude
        FROM weather_readings
        WHERE city = %s AND latitude IS NOT NULL AND longitude IS NOT NULL
        LIMIT 1
    """
    
    cursor.execute(query, (city_normalized,))
    result = cursor.fetchone()
    
    if not result and 'paulo' in city_normalized.lower():
        query = """
            SELECT DISTINCT latitude, longitude
            FROM weather_readings
            WHERE city LIKE %s AND latitude IS NOT NULL AND longitude IS NOT NULL
            LIMIT 1
        """
        cursor.execute(query, ('%Paulo%',))
        result = cursor.fetchone()
    
    if not result:
        query = """
            SELECT DISTINCT latitude, longitude
            FROM weather_readings
            WHERE LOWER(city) = LOWER(%s) AND latitude IS NOT NULL AND longitude IS NOT NULL
            LIMIT 1
        """
        cursor.execute(query, (city_normalized,))
        result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if result:
        print(f"Found coordinates in DB for {city_normalized}: {result}")
        return result
    
    if city_normalized in FALLBACK_COORDINATES:
        coords = FALLBACK_COORDINATES[city_normalized]
        print(f"Using fallback coordinates for {city_normalized}: {coords}")
        return coords
    
    for known_city, coords in FALLBACK_COORDINATES.items():
        if known_city.lower() == city_normalized.lower():
            print(f"Using fallback coordinates for {city_normalized} (matched {known_city}): {coords}")
            return coords
    
    print(f"No coordinates found for {city_normalized}")
    return (None, None)

def fetch_weather_forecast(city_name):
    """Fetch 5-day weather forecast from OpenWeatherMap API"""
    try:
        if not OPENWEATHER_API_KEY:
            return {'error': 'OpenWeatherMap API key not configured'}
        
        lat, lon = get_city_coordinates(city_name)
        
        if not lat or not lon:
            return {'error': f'City coordinates not found for: {city_name}'}
        
        params = {
            'lat': str(lat),
            'lon': str(lon),
            'appid': OPENWEATHER_API_KEY,
            'units': 'imperial',
            'cnt': '40'
        }
        
        url = f"{OPENWEATHER_FORECAST_URL}?{urlencode(params)}"
        
        response = http.request('GET', url, timeout=10.0)
        
        if response.status == 401:
            return {'error': 'Invalid API key - check your OpenWeatherMap API key'}
        
        if response.status != 200:
            return {'error': f'API request failed with status {response.status}'}
        
        data = json.loads(response.data.decode('utf-8'))
        
        forecast_list = []
        for item in data.get('list', []):
            forecast_list.append({
                'timestamp': item['dt_txt'],
                'temperature': item['main']['temp'],
                'feels_like': item['main']['feels_like'],
                'temp_min': item['main']['temp_min'],
                'temp_max': item['main']['temp_max'],
                'humidity': item['main']['humidity'],
                'pressure': item['main']['pressure'],
                'condition': item['weather'][0]['description'],
                'wind_speed': item['wind']['speed'],
                'pop': item.get('pop', 0) * 100
            })
        
        daily_forecast = {}
        for item in forecast_list:
            date = item['timestamp'].split()[0]
            if date not in daily_forecast:
                daily_forecast[date] = []
            daily_forecast[date].append(item)
        
        daily_summary = []
        for date, items in sorted(daily_forecast.items()):
            temps = [i['temperature'] for i in items]
            daily_summary.append({
                'date': date,
                'temp_min': min(temps),
                'temp_max': max(temps),
                'temp_avg': sum(temps) / len(temps),
                'condition': items[len(items)//2]['condition'],
                'humidity_avg': sum(i['humidity'] for i in items) / len(items),
                'wind_speed_avg': sum(i['wind_speed'] for i in items) / len(items),
                'pop_max': max(i['pop'] for i in items)
            })
        
        return {
            'city': city_name,
            'hourly': forecast_list[:24],
            'daily': daily_summary[:5]
        }
        
    except urllib3.exceptions.HTTPError as e:
        return {'error': f'HTTP error: {str(e)}'}
    except urllib3.exceptions.TimeoutError:
        return {'error': 'Request timeout - API did not respond in time'}
    except json.JSONDecodeError as e:
        return {'error': f'Failed to parse API response: {str(e)}'}
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return {'error': f'Error: {str(e)}', 'trace': error_trace}

def lambda_handler(event, context):
    """Lambda handler for forecast requests"""
    
    print(f"Event received: {json.dumps(event)}")
    
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET, OPTIONS'
            },
            'body': ''
        }
    
    city = None
    
    if event.get('pathParameters'):
        city = event['pathParameters'].get('city')
        print(f"City from path parameters: {city}")
    
    if not city and event.get('queryStringParameters'):
        city = event['queryStringParameters'].get('city')
        print(f"City from query parameters: {city}")
    
    if not city and event.get('body'):
        try:
            body = json.loads(event['body'])
            city = body.get('city')
            print(f"City from body: {city}")
        except:
            pass
    
    if not city:
        print("ERROR: No city parameter found in request")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'City parameter required',
                'help': 'Use /forecast/{city} or ?city={city}'
            })
        }
    
    print(f"Processing forecast request for city: {city}")
    
    city = normalize_city_name(city)
    print(f"Normalized city name: {city}")
    
    forecast_data = fetch_weather_forecast(city)
    
    if 'error' in forecast_data:
        print(f"Error in forecast: {forecast_data['error']}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(forecast_data)
        }
    
    print(f"Successfully fetched forecast for {city}")
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(forecast_data)
    }