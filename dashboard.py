from flask import Flask, render_template, jsonify
import requests
import subprocess
import psutil
import json
import datetime
import pytz
app = Flask(__name__)

with open('api_keys.json') as f:
  api_keys = json.load(f)
# Replace with your actual API keys
OPENWEATHER_API_KEY = api_keys['OPENWEATHER_API_KEY'] #'your_openweather_api_key'
DE_LIJN_API_KEY = api_keys['DE_LIJN_API_KEY'] #'your_de_lijn_api_key'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data():
    weather = get_weather()
    bus = get_bus_times()
    train = get_train_schedule()
    uptime = get_system_uptime()
    lan_ip,wifi_status = get_network_info()
    # Extracting specific weather data (icon, temp, sunrise, sunset)
    weather_data = {
        'description': weather['weather'][0]['description'],
        'icon': weather['weather'][0]['icon'],
        'temp': weather['main']['temp'],
        'sunrise': get_local_time(weather['sys']['sunrise']),
        'sunset': get_local_time(weather['sys']['sunset'])
    }
    pihole = get_pihole_status()
    print(f'{jsonify(weather=weather_data, bus=bus, train=train, uptime=uptime, lan=lan_ip, wifi=wifi_status, pihole=pihole)}')
    return jsonify(weather=weather_data, bus=bus, train=train, uptime=uptime, lan=lan_ip, wifi=wifi_status, pihole=pihole)


import shutil
import subprocess

def get_pihole_status():
    """
    Checks if the 'pihole' command is available and if Pi-hole blocking is enabled.

    Returns:
        str: "Enabled" if Pi-hole command is found and blocking is enabled,
             "NA" otherwise (not found, not enabled, or error).
    """
    # 1. Check if the 'pihole' command exists in the system's PATH
    pihole_path = shutil.which('pihole')

    if pihole_path is None:
        # print("pihole command not found in PATH.")
        return "NA"

    try:
        # 2. Run the 'pihole status' command
        # Use the full path found by shutil.which for robustness
        # Add a timeout (e.g., 10 seconds) to prevent hanging
        result = subprocess.run(
            [pihole_path, 'status'],
            capture_output=True,  # Capture stdout and stderr
            text=True,            # Decode output as text
            check=False,          # Don't raise exception on non-zero exit code
            timeout=10
        )

        # 3. Check the output for the specific string
        # We check stdout specifically, as stderr might contain warnings
        if result.stdout and 'Pi-hole blocking is enabled' in result.stdout:
            return "Enabled"
        else:
            # String not found in stdout, or stdout was empty
            # This covers cases where it's disabled or has unexpected output
            # print(f"Pi-hole status output did not confirm enabled:\n{result.stdout}")
            return "NA"

    except FileNotFoundError:
        # This shouldn't happen often if shutil.which found it, but good practice
        # print(f"Error: pihole command not found at {pihole_path} despite shutil.which.")
        return "NA"
    except subprocess.TimeoutExpired:
        print("Error: Timeout expired while running 'pihole status'.")
        return "NA"
    except Exception as e:
        # Catch any other unexpected errors during subprocess execution
        print(f"An unexpected error occurred while checking Pi-hole status: {e}")
        return "NA"


def get_local_time(t_string):
  t_stamp = datetime.datetime.fromtimestamp(int(t_string), tz=pytz.UTC)
  # Use the Brussels timezone
  local_timezone = pytz.timezone('Europe/Brussels')
  return f'{t_stamp.astimezone(local_timezone)}'

def get_network_info():
    # Get network stats
    networks = psutil.net_if_addrs()
    lan_info = None
    wifi_info = None

    for interface, addrs in networks.items():
        for addr in addrs:
            if addr.family == psutil.socket.AF_INET:
                if "eth" in interface:  # Assuming LAN is eth0 or similar
                    lan_info = f"{interface}: {addr.address}"
                elif "wlan" in interface or 'en0' in interface:  # Assuming WiFi is wlan0 or similar
                    wifi_info = f"{interface}: {addr.address}"

    lan = lan_info if lan_info else "Not connected"
    wifi = wifi_info if wifi_info else "Not connected"
    print(lan, wifi)
    return lan, wifi

def get_weather():
    if not OPENWEATHER_API_KEY:
       return 'NA'
    city = 'Leuven'
    url = f'https://api.openweathermap.org/data/2.5/weather?lat={50.8791}&lon={4.7025}&appid={OPENWEATHER_API_KEY}'
    response = requests.get(url)
    data = response.json()

    if response.status_code == 200:
        return data
    else:
        print(response)
        return None
def format_connection_string(dirname, name, departure_time, departure_delay, widths):
  """Formats a connection string with fixed-width fields.

  Args:
    dirname: The directory name.
    name: The connection name.
    departure_time: The departure time.
    departure_delay: The departure delay in minutes.
    widths: A list of integers representing the desired widths for each field.

  Returns:
    A formatted string with fixed-width fields.
  """
  fields = [dirname, name, departure_time, f"{departure_delay}mins"]
  formatted_fields = []

  for field, width in zip(fields, widths):
    formatted_fields.append(f"{field:<{width}}")  # Left-align and pad with spaces
  formatted_fields[0] = formatted_fields[0]+'\n'
  return "|".join(formatted_fields)
def get_bus_times():
    if not DE_LIJN_API_KEY:
       return ['tick tock']
    stop_id = '306279'  # Replace with your actual stop ID
    url = f'https://api.delijn.be/DL/OpenData/Realtime/StopDepartures/{stop_id}'
    headers = {'Ocp-Apim-Subscription-Key': DE_LIJN_API_KEY}
    response = requests.get(url, headers=headers)
    data = response.json()


    if response.status_code == 200 and 'departures' in data:
        departures = data['departures']['departure']
        if departures:
            next_bus = departures[0]
            line = next_bus['lineNumberPublic']
            destination = next_bus['destination']
            due_in = next_bus['departureTime']['expectedDepartureTime']
            return [f"Line {line} to {destination} in {due_in} minutes"]
    print('bus:',response)
    return ["Bus data unavailable"]

def get_train_schedule():
    from_station = 'Leuven'
    to_station = 'Brussels-North'
    url = f'https://api.irail.be/connections/?from={from_station}&to={to_station}&format=json'
    response = requests.get(url)
    data = response.json()
    if response.status_code != 200:
        return ["Train data unavailable"]

    data = response.json()
    if 'connection' not in data:
        return ["Train data unavailable"]

    connections = data['connection']
    if not connections:
        return ["No upcoming trains"]
    if response.status_code == 200 and 'connection' in data:
        connections = data['connection']
        if connections:
            all_conn = []
            for next_train in connections[:3]:

              departure_time = datetime.datetime.fromtimestamp(int(next_train['departure']['time'])).strftime('%H:%M')
              departure_delay = int(next_train['departure']['delay']) // 60
              name = next_train['departure']['vehicleinfo']['shortname']
              dirname = next_train['departure']['direction']['name']
              widths = [10, 15, 8, 10]  # Example widths for each field
              fcs = format_connection_string(dirname, name, departure_time, departure_delay, widths)
              all_conn.append(fcs)
            return all_conn
    return ["Train data unavailable"]

def get_system_uptime():
    uptime = subprocess.check_output('uptime', shell=True).decode().strip()
    return uptime

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
