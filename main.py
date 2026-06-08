from machine import Pin
import time

# Trage hier die GP-Nummer ein, wo das Kabel AM PICO steckt!
relais = Pin(15, Pin.OUT) 

print("Starte reinen Power-Test...")

try:
    while True:
        print("Schalte Pin auf HIGH (3.3V)")
        relais.value(1)
        time.sleep(2)
        
        print("Schalte Pin auf LOW (0V)")
        relais.value(0)
        time.sleep(2)

except KeyboardInterrupt:
    print("Test beendet.")
