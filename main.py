from machine import Pin
import time

# ==========================================
# CONFIGURATION & SETUP
# ==========================================

# 1. Intervals (in milliseconds for the Pico)
MEASUREMENT_INTERVAL = 30 * 1000   # Check sensors every 30 seconds
TODO_WAIT_TIME = 10 * 1000         # ToDo must be 10 seconds old before triggering
VALVE_OPEN_DURATION = 5 * 1000     # Valves stay open for 5 seconds

# 2. Sensor Array (Currently only one sensor on GP16)
# Assumption: Sensor returns 0 for dry (no water) and 1 for wet (full)
sensors = [
    Pin(16, Pin.IN, Pin.PULL_DOWN)
]

# 3. Mapping: Which sensor controls which relay pin?
# Format: { Sensor_Pin_Object: Relay_Pin_Number }
sensor_to_relay = {
    sensors[0]: 15  # Sensor on GP16 controls the relay on GP15
}

# 4. Global storage for initialized relay objects
relay_objects = {}
for pin_num in sensor_to_relay.values():
    # Initial state: Safely OFF (configured as INPUT to draw 0 current)
    relay_objects[pin_num] = Pin(pin_num, Pin.IN)

# 5. The ToDo dictionary for delayed valve activation
# Structure: { Relay_Pin_Number: Timestamp_Of_Creation }
valve_todos = {}

# Timestamp for the main measurement loop
last_measurement = time.ticks_ms()

print("Application started. Sensor monitoring active...")

# Helper functions for clean relay switching
def open_valve(pin_num):
    print(f"-> Switching relay on Pin {pin_num} ON (Valve OPENS)")
    relay_objects[pin_num].init(Pin.OUT)
    relay_objects[pin_num].value(0) # Switches the active-low relay to GND

def close_valve(pin_num):
    print(f"-> Switching relay on Pin {pin_num} OFF (Valve CLOSES)")
    relay_objects[pin_num].init(Pin.IN)

# ==========================================
# MAIN LOOP
# ==========================================
try:
    while True:
        now = time.ticks_ms()
        
        # --------------------------------------------------
        # LOOP 1: Sensor Check (Every 30 seconds)
        # --------------------------------------------------
        if time.ticks_diff(now, last_measurement) >= MEASUREMENT_INTERVAL:
            print("\n--- Starting Sensor Check ---")
            
            for sensor in sensors:
                status = sensor.value()
                assigned_relay = sensor_to_relay[sensor]
                
                if status == 0:
                    # SENSOR REPORTS NO WATER
                    if assigned_relay not in valve_todos:
                        print(f"Sensor {sensor}: No water! Creating ToDo for relay {assigned_relay}.")
                        valve_todos[assigned_relay] = time.ticks_ms()
                    else:
                        print(f"Sensor {sensor}: Still no water. ToDo already exists.")
                        
                else:
                    # SENSOR REPORTS FULL
                    if assigned_relay in valve_todos:
                        print(f"Sensor {sensor}: Water detected! Deleting ToDo for relay {assigned_relay}.")
                        del valve_todos[assigned_relay]
                    else:
                        print(f"Sensor {sensor}: Status OK (full). No action needed.")
            
            # Update timestamp for the next interval
            last_measurement = now

        # --------------------------------------------------
        # LOOP 2: ToDo Check & Sequence Execution
        # --------------------------------------------------
        if valve_todos:
            current_time = time.ticks_ms()
            trigger_valves = False
            
            # Check if ANY ToDo is older than 10 seconds
            for relay_pin, timestamp in list(valve_todos.items()):
                if time.ticks_diff(current_time, timestamp) >= TODO_WAIT_TIME:
                    print(f"The ToDo for relay {relay_pin} is older than 10 seconds!")
                    trigger_valves = True
                    break # One expired ToDo is enough to trigger the sequence
            
            # If the condition is met, execute the safety sequence
            if trigger_valves:
                print("!!! Action triggered: Opening ALL affected valves !!!")
                
                # 1. Open all valves that had an active ToDo
                opened_valves = []
                for relay_pin in list(valve_todos.keys()):
                    open_valve(relay_pin)
                    opened_valves.append(relay_pin)
                    # ToDo is handled, remove it from the dictionary
                    del valve_todos[relay_pin]
                
                # 2. Wait for the configurable duration X (5 seconds)
                print(f"Keeping valves open for {VALVE_OPEN_DURATION / 1000} seconds...")
                time.sleep_ms(VALVE_OPEN_DURATION)
                
                # 3. Close all valves that were opened in this sequence
                print("Closing all opened valves.")
                for relay_pin in opened_valves:
                    close_valve(relay_pin)
                
                print("Sequence finished. Resuming normal operations.\n")
                # Reset main timestamp so we don't measure mid-cycle
                last_measurement = time.ticks_ms()

        # Small pause to prevent the CPU from running at 100% load
        time.sleep_ms(100)

except KeyboardInterrupt:
    print("Program stopped by user. Safely closing all valves.")
    for pin_num in sensor_to_relay.values():
        close_valve(pin_num)