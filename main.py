from machine import Pin
import time
import os
import urequests
import socket

# ==========================================
# CONFIGURATION & SETUP
# ==========================================

# 1. Intervals (in milliseconds for the Pico)
MEASUREMENT_INTERVAL = 1 * 60 * 1000     # Check sensors every x seconds
TODO_WAIT_TIME = 15 * 60 *  1000          # ToDo triggers immediately (0s) for testing
VALVE_OPEN_DURATION = 90  * 1000     # Valves stay open for 5 seconds
CONSTANT_WATER_ALARM = 8 * 60 * 60 * 1000  # 8 hours in milliseconds (Test tip: set to 20 * 1000 for 20s test!)
#CONSTANT_WATER_ALARM = 8 * 3600 * 1000  # 8 hours in milliseconds (Test tip: set to 20 * 1000 for 20s test!)
# Trage hier die IP-Adresse deines PCs ein!
PC_SERVER_URL = "http://192.168.178.81:5100/log"
TARGET_IP = "192.168.178.81"
TARGET_PORT = 5005
LOG_FILE = "app_log.txt"

# 2. Sensor Array
sensors = [
    Pin(16, Pin.IN, Pin.PULL_DOWN)
]

# 3. Mapping: Which sensor controls which relay pin?
sensor_to_relay = {
    sensors[0]: 15
}

# 4. Global storage for initialized relay objects
relay_objects = {}
for pin_num in sensor_to_relay.values():
    relay_objects[pin_num] = Pin(pin_num, Pin.IN)

# 5. Dictionaries for states and timestamps
valve_todos = {}
water_start_timestamps = {}  # Tracks when a sensor started seeing water continuously

last_measurement = time.ticks_ms()

# ==========================================
# LOGGING HELPER FUNCTIONS
# ==========================================

def log_event(message):
    """Writes to file, console, and sends it to the local PC server with safety timeout."""
    uptime_sec = time.ticks_ms() // 1000
    log_entry = f"[{uptime_sec}s] {message}"
    print(log_entry)
    
    try:
        sock.sendto(message.encode(), (TARGET_IP, TARGET_PORT))
    except Exception as e:
        print("Netzwerk-Log fehlgeschlagen:", e)
    
    # 1. Local File-Log
    #try:
    #    with open(LOG_FILE, "a") as f:
    #        f.write(log_entry + "\n")
    #except Exception as e:
    #    print(f"Failed to write to log file: {e}")
        
    # 2. Absolut sicherer Live-Funk an den PC-Server
    #try:
    #    # timeout=2 verhindert, dass der Pico unendlich blockiert, falls der PC zickt
    #    response = urequests.post(PC_SERVER_URL, data=log_entry, timeout=2.0)
    #    response.close() # Wichtig für den RAM
    #except Exception as e:
    #    # Falls der Server blockiert, ignorieren wir das im Hauptprogramm
    #    print(f"Network log failed (Server offline/blocked): {e}")

def get_and_clear_log():
    """Called by your web client later to fetch logs and wipe the file."""
    if LOG_FILE not in os.listdir():
        return "No logs available."
    
    try:
        with open(LOG_FILE, "r") as f:
            content = f.read()
        os.remove(LOG_FILE) # Wipes the file from flash after reading
        return content
    except Exception as e:
        return f"Error managing log file: {e}"

# Initial application start log
log_event("Application started. Sensor monitoring active...")

# Helper functions for clean relay switching
def open_valve(pin_num):
    log_event(f"Switching relay on Pin {pin_num} ON (Valve OPENS)")
    relay_objects[pin_num].init(Pin.OUT)
    relay_objects[pin_num].value(0)

def close_valve(pin_num):
    log_event(f"Switching relay on Pin {pin_num} OFF (Valve CLOSES)")
    relay_objects[pin_num].init(Pin.IN)

# ==========================================
# MAIN LOOP
# ==========================================
def run_main_loop():
    firstRun = True
    log_event("Entering main loop")
    #Put the entire while True loop inside this function.
    global last_measurement # Needed to modify the global timestamp
    try:
        while True:
            now = time.ticks_ms()
            
            # --------------------------------------------------
            # LOOP 1: Sensor Check
            # --------------------------------------------------
            if firstRun or time.ticks_diff(now, last_measurement) >= MEASUREMENT_INTERVAL:
                firstRun = False
                log_event("Checking Sensors")
                for sensor in sensors:
                    log_event(f"Checking Sensor {sensor}")
                    status = sensor.value()
                    assigned_relay = sensor_to_relay[sensor]
                    
                    if status == 1:
                        # SENSOR REPORTS NO WATER
                        water_start_timestamps.pop(sensor, None) # Clear water timer immediately
                        
                        if assigned_relay not in valve_todos:
                            log_event(f"Sensor {sensor}: No water detected! Creating ToDo for relay {assigned_relay}.")
                            valve_todos[assigned_relay] = time.ticks_ms()
                            
                    else:
                        # SENSOR REPORTS FULL / WATER DETECTED
                        if assigned_relay in valve_todos:
                            log_event(f"Sensor {sensor}: Water detected! Deleting ToDo for relay {assigned_relay}.")
                            del valve_todos[assigned_relay]
                        
                        # 8-Hour Constant Water Check
                        if sensor not in water_start_timestamps:
                            # First time seeing water, start tracking the time
                            water_start_timestamps[sensor] = time.ticks_ms()
                        else:
                            # Sensor is continuously wet, check how long
                            duration = time.ticks_diff(time.ticks_ms(), water_start_timestamps[sensor])
                            if duration >= CONSTANT_WATER_ALARM:
                                log_event(f"WARNING: Sensor {sensor} has reported constant water for over 8 hours!")
                                # Optional: Reset timer here if you don't want it to spam every 5 seconds
                                # water_start_timestamps[sensor] = time.ticks_ms()
                
                last_measurement = now

            # --------------------------------------------------
            # LOOP 2: ToDo Check & Sequence Execution
            # --------------------------------------------------
            if valve_todos:
                current_time = time.ticks_ms()
                trigger_valves = False
                
                for relay_pin, timestamp in list(valve_todos.items()):
                    if time.ticks_diff(current_time, timestamp) >= TODO_WAIT_TIME:
                        log_event(f"The ToDo for relay {relay_pin} has expired the wait time constraint.")
                        trigger_valves = True
                        break
                
                if trigger_valves:
                    log_event("!!! Safety Sequence Triggered: Opening ALL affected valves !!!")
                    
                    opened_valves = []
                    for relay_pin in list(valve_todos.keys()):
                        open_valve(relay_pin)
                        opened_valves.append(relay_pin)
                        del valve_todos[relay_pin]
                    
                    log_event(f"Holding valves open for {VALVE_OPEN_DURATION / 1000} seconds...")
                    time.sleep_ms(VALVE_OPEN_DURATION)
                    
                    log_event("Closing all opened valves.")
                    for relay_pin in opened_valves:
                        close_valve(relay_pin)
                    
                    log_event("Sequence finished. Resuming normal operations.")
                    last_measurement = time.ticks_ms()

            time.sleep_ms(100)

    except KeyboardInterrupt:
        log_event("Program stopped by user. Safely closing all valves.")
        for pin_num in sensor_to_relay.values():
            close_valve(pin_num)
    
        # ==========================================
# THE IMPORT PROTECTION
# ==========================================
if __name__ == "__main__":
    # This only runs if you press "Play" in Thonny or if the file is named main.py
    run_main_loop()

