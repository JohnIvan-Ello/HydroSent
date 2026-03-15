main.py/////////////////////////////////////////////////////////////

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk
import logging

import config
from config import get_model
model = get_model()

import tc_thread
import cw_thread
from sensors_thread import sensor_loop, command_loop, camera_loop
from hm_thread import hm_loop

from ultralytics import YOLO

# ====== Globals ======
command = {
    "motorL": 0,
    "motorR": 0,
    "servo": 90,
    "e": 0,
}
status_label = None

def build_command(data: dict) -> str:
    return ",".join(f"{k}:{v}" for k, v in data.items())

def set_toggle(name, var):
    config.gui_flags[name] = 1 if var.get() else 0
    print(f"[Toggle] {name} set to {config.gui_flags[name]}")

def move(direction, throttle_scale):
    speed = throttle_scale.get()
    if direction == "forward":
        command["motorL"] = speed
        command["motorR"] = speed
    elif direction == "backward":
        command["motorL"] = -speed
        command["motorR"] = -speed
    elif direction == "left":
        command["motorL"] = -speed
        command["motorR"] = speed
    elif direction == "right":
        command["motorL"] = speed
        command["motorR"] = -speed
    elif direction == "stop":
        command["motorL"] = 0
        command["motorR"] = 0

def safety_stop_loop():
    while True:
        time.sleep(1.5)
        if not any(config.gui_flags.get(mode, 0) for mode in ["CW", "TC", "HM"]):
            if command["motorL"] != 0 or command["motorR"] != 0:
                print("[Safety] No mode active, stopping motors")
                command["motorL"] = 0
                command["motorR"] = 0

def start_gui():
    threading.Thread(target=sensor_loop, daemon=True).start()
    threading.Thread(target=camera_loop, daemon=True).start()

    root = tk.Tk()
    root.title("Hydrosent Control")
    main_frame = ttk.Frame(root, padding="10")
    main_frame.grid(row=0, column=0)

    # === Toggle Modes ===
    toggle_frame = ttk.LabelFrame(main_frame, text="Modes")
    toggle_frame.grid(row=0, column=0, padx=10)
    for label in ["CW", "TC", "HM"]:
        var = tk.IntVar()
        check = ttk.Checkbutton(toggle_frame, text=label, variable=var,
                                command=lambda l=label, v=var: set_toggle(l, v))
        check.pack(anchor="w")

    # === Movement Section ===
    ctrl_frame = ttk.LabelFrame(main_frame, text="Movement")
    ctrl_frame.grid(row=0, column=1, padx=10)

    throttle_scale = tk.Scale(ctrl_frame, from_=255, to=0, orient="vertical", label="Throttle")
    throttle_scale.set(200)
    throttle_scale.grid(row=0, column=0, rowspan=4, padx=5)

    servo_scale = tk.Scale(ctrl_frame, from_=80, to=60, orient="vertical", label="Servo")
    servo_scale.set(90)
    servo_scale.grid(row=0, column=1, rowspan=4, padx=5)
    servo_scale.config(command=lambda val: command.update({"servo": int(val)}))

    button_frame = ttk.Frame(ctrl_frame)
    button_frame.grid(row=0, column=2, rowspan=3)

    ttk.Button(button_frame, text="↑", width=8, command=lambda: move("forward", throttle_scale)).grid(row=0, column=1)
    ttk.Button(button_frame, text="←", width=8, command=lambda: move("left", throttle_scale)).grid(row=1, column=0)
    ttk.Button(button_frame, text="STOP", width=8, command=lambda: move("stop", throttle_scale)).grid(row=1, column=1)
    ttk.Button(button_frame, text="→", width=8, command=lambda: move("right", throttle_scale)).grid(row=1, column=2)
    ttk.Button(button_frame, text="↓", width=8, command=lambda: move("backward", throttle_scale)).grid(row=2, column=1)

    def toggle_e():
        command["e"] = 0 if command["e"] == 1 else 1
        cb_button.config(text=f"CB ({command['e']})")

    cb_button = ttk.Button(ctrl_frame, text="CB (0)", width=8, command=toggle_e)
    cb_button.grid(row=1, column=3, padx=5)

    global status_label
    status_label = ttk.Label(root, text="Waiting for GPS...", anchor="e", foreground="orange")
    status_label.grid(row=1, column=0, sticky="se", padx=10, pady=5)
    config.set_status_label(status_label)

    # Start logic threads
    threading.Thread(target=command_loop, args=(build_command, command), daemon=True).start()
    threading.Thread(target=cw_thread.cw_loop, args=(build_command, command), daemon=True).start()
    threading.Thread(target=tc_thread.tc_loop, args=(build_command, command), daemon=True).start()
    threading.Thread(target=hm_loop, args=(build_command, command), daemon=True).start()
    threading.Thread(target=safety_stop_loop, daemon=True).start()

    root.mainloop()

# ====== MAIN ENTRY POINT ======
if __name__ == "__main__":
    try:
        logging.getLogger('ultralytics').setLevel(logging.CRITICAL)
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        model_path = os.path.join(base_path, "best.pt")
        model = YOLO(model_path)
        config.model = model  # if shared

        start_gui()
    except Exception as e:
        print(f"[Startup Error] {e}")
        time.sleep(10)  # Pause so user can read error in .exe window


config.py/////////////////////////////////////////////////////////////////////////

import os
import sys
import logging

# --- Base Path Detection for PyInstaller ---
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# --- Shared State ---
gui_flags = {
    "CW": 0,
    "TC": 0,
    "HM": 0
}
# Default values to prevent AttributeError on first access
last_sensor_data = {}  # Dictionary of the latest sensor readings
current_wp_name = ""   # Currently targeted waypoint name (e.g., "A", "B", ...)

detected_trash = []  # Each entry: (cx, cy, width, height, class_name)
home_saved = False
status_label = None
current_heading = "H---"

# --- Model Lazy-Loader ---
_model = None
def get_model():
    global _model
    if _model is None:
        try:
            from ultralytics import YOLO
            model_path = os.path.join(base_path, "best.pt")
            _model = YOLO(model_path)
        except Exception as e:
            logging.error(f"[Config] Failed to load model: {e}")
            _model = None
    return _model

# --- ESP32 Endpoint URLs ---
ESP32_IP = "http://192.168.1.100"
CAM_URL = f"{ESP32_IP}/cam-hi.jpg"
SENSOR_URL = f"{ESP32_IP}/sensors"
COMMAND_URL = f"{ESP32_IP}/command"

# --- Shared Updaters ---
def set_home_saved(val=True):
    global home_saved
    home_saved = val

def set_status_label(widget):
    global status_label
    status_label = widget

def update_heading(new_heading):
    global current_heading
    current_heading = new_heading

sensors_thread.py//////////////////////////////////////////////////////////////
import time
import requests
import os
import json
import numpy as np
import cv2
import math
import config

CAM_URL = f"{config.ESP32_IP}/cam-hi.jpg"
SENSOR_URL = f"{config.ESP32_IP}/sensors"
COMMAND_URL = f"{config.ESP32_IP}/command"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371e3
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2)**2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def sensor_loop():
    last_wp_info = ""
    last_lat = None
    last_lng = None

    while True:
        try:
            response = requests.get(SENSOR_URL, timeout=3)
            if response.status_code != 200:
                raise ValueError("Bad response")

            raw_text = response.text.strip()
            print("[Sensor]", raw_text)

            parts = dict(part.split(":") for part in raw_text.split(",") if ":" in part)
            config.last_sensor_data = parts

            battery = int(parts.get("battery", 100))
            label = config.status_label
            home_saved_now = config.home_saved

            # Save home waypoint if GPS is valid
            if not config.home_saved and all(k in parts for k in ["gps_sat", "hdop", "lat", "lng"]):
                try:
                    sats = int(parts["gps_sat"])
                    hdop = float(parts["hdop"])
                    lat = float(parts["lat"])
                    lng = float(parts["lng"])
                    if sats >= 4 and hdop <= 2.5:
                        wp_file = os.path.join(config.base_path, "waypoints.json")
                        data = {}
                        if os.path.exists(wp_file):
                            with open(wp_file, "r") as f:
                                data = json.load(f)
                        data["h"] = [lat, lng]
                        with open(wp_file, "w") as f:
                            json.dump(data, f, indent=2)

                        config.set_home_saved(True)
                        home_saved_now = True
                        print("[Waypoint] Home saved:", lat, lng)
                except Exception:
                    pass

            # Update heading display
            if "heading" in parts:
                config.update_heading(parts["heading"])

            # --- GUI Status Label Update ---
            battery_str = f"⚠️ Low Battery: {battery}%" if battery < 20 else f"Battery: {battery}%"
            home_str = "✅ Checks Complete" if home_saved_now else "⏳ GPS Fixing..."

            wp_info = last_wp_info  # default

            if config.gui_flags.get("TC", 0) or config.gui_flags.get("HM", 0) or config.gui_flags.get("CW", 0):
                wp_name = getattr(config, "current_wp_name", "")
                
                # Update last known lat/lng if new ones are available
                if "lat" in parts and "lng" in parts:
                    try:
                        last_lat = float(parts["lat"])
                        last_lng = float(parts["lng"])
                    except:
                        pass

                # Compute distance if we have cached lat/lng
                if wp_name and last_lat is not None and last_lng is not None:
                    try:
                        wp_file = os.path.join(config.base_path, "waypoints.json")
                        if os.path.exists(wp_file):
                            with open(wp_file, "r") as f:
                                wp_data = json.load(f)
                            if wp_name in wp_data:
                                wp_lat, wp_lng = wp_data[wp_name]
                                dist = haversine(last_lat, last_lng, wp_lat, wp_lng)
                                wp_info = f" | WP: {wp_name} ({dist:.1f}m)"
                                last_wp_info = wp_info
                    except Exception as e:
                        print("[Sensor] Waypoint info error:", e)

            label_text = f"{battery_str} | {home_str}{wp_info}"
            label.after(0, lambda: label.config(text=label_text, foreground="red" if battery < 20 else "green"))

        except Exception as e:
            print("[Sensor Error]:", e)

        time.sleep(0.2)




def command_loop(build_command, command):
    last_cmd_str = ""
    while True:
        try:
            cmd_str = build_command(command)
            if cmd_str != last_cmd_str:
                response = requests.post(COMMAND_URL, data=cmd_str,
                                         headers={"Content-Type": "text/plain"}, timeout=3)
                if response.status_code == 200:
                    print("[Command]", cmd_str)
                    last_cmd_str = cmd_str
        except Exception as e:
            print("[Command Error]:", e)

        time.sleep(0.2)


def camera_loop():
    TRASH_CLASSES = {"plastic", "glass", "metal"}
    model = config.get_model()

    while True:
        try:
            response = requests.get(CAM_URL, timeout=3)
            if response.status_code != 200:
                raise ValueError("Failed to fetch image")

            img_array = np.frombuffer(response.content, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("Image decode failed")

            results = model(frame)
            boxes = results[0].boxes
            config.detected_trash.clear()

            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                w = int(x2 - x1)
                h = int(y2 - y1)
                cx = int(x1 + w / 2)
                cy = int(y1 + h / 2)
                class_id = int(box.cls[0])
                class_name = results[0].names[class_id].lower()

                if class_name in TRASH_CLASSES:
                    config.detected_trash.append((cx, cy, w, h, class_name))

                cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)
                label = f"{class_name} ({cx},{cy}) {w}x{h}"
                cv2.putText(frame, label, (cx - 50, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            annotated = results[0].plot()
            blended = cv2.addWeighted(annotated, 0.7, frame, 0.3, 0)

            h, w = frame.shape[:2]
            config.frame_width = w
            config.frame_height = h

            cv2.putText(blended, config.current_heading, (w // 2 - 80, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

            cv2.imshow("Trash Detection", blended)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        except Exception as e:
            print("[Camera Error]:", e)

        time.sleep(0.1)

    cv2.destroyAllWindows()


cw_thread.py////////////////////////////////////////////////////////////////
import time
import math
import json
import os
import requests
import config

# Determine the correct path regardless of PyInstaller or script run
if getattr(__import__('sys'), 'frozen', False):
    base_path = __import__('sys')._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

WAYPOINT_FILE = os.path.join(base_path, "waypoints.json")
COMMAND_URL = f"{config.ESP32_IP}/command"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371e3  # meters
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2)**2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_bearing(lat1, lon1, lat2, lon2):
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    y = math.sin(Δλ) * math.cos(φ2)
    x = math.cos(φ1) * math.sin(φ2) - math.sin(φ1) * math.cos(φ2) * math.cos(Δλ)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def cw_loop(build_command, command):
    current_index = 0
    waypoints = []

    last_lat = None
    last_lng = None

    # --- Load waypoints ---
    try:
        with open(WAYPOINT_FILE, "r") as f:
            data = json.load(f)
            waypoints = [(k, v) for k, v in data.items() if k != "h"]
            print("[CW] Loaded waypoints:")
            for name, coords in waypoints:
                print(f"  {name}: {coords}, type: {type(coords)}")

            waypoints.sort()  # Sort alphabetically
    except Exception as e:
        print("[CW] Failed to load waypoints:", e)
        return

    if not waypoints:
        print("[CW] No waypoints to follow.")
        return

    # --- CW Mode Loop ---
    while True:
        if not config.gui_flags.get("CW", 0):
            time.sleep(2)
            continue

        try:
            parts = config.last_sensor_data.copy()

            # --- IR Trigger for Homing ---
            try:
                if int(parts.get("IR", 0)) == 1:
                    print("[CW] Triggering Homing — Reason: IR Triggered")
                    config.gui_flags["CW"] = 0
                    config.gui_flags["HM"] = 1
                    continue
            except Exception as e:
                print("[CW] IR check error:", e)

            wp_name, (wlat, wlng) = waypoints[current_index]
            config.current_wp_name = wp_name

            # --- Cache GPS if present ---
            if "lat" in parts and "lng" in parts:
                try:
                    last_lat = float(parts["lat"])
                    last_lng = float(parts["lng"])
                except:
                    pass

            # --- Proceed only if heading is available and GPS was cached ---
            if "heading" in parts and last_lat is not None and last_lng is not None:
                heading = float(parts["heading"])

                print(f"[DEBUG] Current: lat={last_lat}, lng={last_lng}")
                print(f"[DEBUG] Target: wlat={wlat}, wlng={wlng}")
                print(f"[DEBUG] Types: {type(wlat)}, {type(wlng)}")

                dist = haversine(last_lat, last_lng, wlat, wlng)
                print(f"[DEBUG] Raw Distance: {dist:.1f} meters")

                bearing = calculate_bearing(last_lat, last_lng, wlat, wlng)
                turn_angle = (bearing - heading + 360) % 360

                print(f"[CW] WP:{wp_name} Dist:{dist:.1f}m Turn:{turn_angle:.1f}°")

                if dist < 5:
                    print(f"[CW] Reached {wp_name}")
                    current_index = (current_index + 1) % len(waypoints)
                    continue

                # --- Navigation Decision ---
                speed = 120
                if turn_angle < 15 or turn_angle > 345:
                    command["motorL"] = speed
                    command["motorR"] = speed
                elif 15 <= turn_angle <= 180:
                    command["motorL"] = speed
                    command["motorR"] = 0
                else:
                    command["motorL"] = 0
                    command["motorR"] = speed

                cmd_str = build_command(command)
                requests.post(COMMAND_URL, data=cmd_str,
                              headers={"Content-Type": "text/plain"}, timeout=3)

        except Exception as e:
            print("[CW] Error:", e)

        time.sleep(0.5)

hm_thread.py////////////////////////////////////////////////////////////////////
import time
import math
import json
import os
import sys
import requests
import config

# PyInstaller-safe path resolution
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

WAYPOINT_FILE = os.path.join(base_path, "waypoints.json")
COMMAND_URL = f"{config.ESP32_IP}/command"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371e3
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_bearing(lat1, lon1, lat2, lon2):
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    y = math.sin(Δλ) * math.cos(φ2)
    x = math.cos(φ1)*math.sin(φ2) - math.sin(φ1)*math.cos(φ2)*math.cos(Δλ)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def hm_loop(build_command, command):
    try:
        with open(WAYPOINT_FILE, "r") as f:
            data = json.load(f)
            if "h" not in data:
                print("[HM] No home waypoint found.")
                return
            hlat, hlng = data["h"]
    except Exception as e:
        print("[HM] Failed to load home waypoint:", e)
        return

    last_lat = None
    last_lng = None

    while True:
        if not config.gui_flags.get("HM"):
            time.sleep(2)
            continue

        try:
            parts = config.last_sensor_data.copy()

            if "heading" not in parts:
                time.sleep(0.5)
                continue  # We need at least heading

            heading = float(parts["heading"])

            if "lat" in parts and "lng" in parts:
                last_lat = float(parts["lat"])
                last_lng = float(parts["lng"])

            if last_lat is not None and last_lng is not None:
                dist = haversine(last_lat, last_lng, hlat, hlng)
                bearing = calculate_bearing(last_lat, last_lng, hlat, hlng)
                turn_angle = (bearing - heading + 360) % 360

                config.current_wp_name = "h"
                print(f"[HM] Home Dist:{dist:.1f}m Turn:{turn_angle:.1f}°")

                if dist < 5:
                    print("[HM] Reached home.")
                    command["motorL"] = 0
                    command["motorR"] = 0
                    config.gui_flags["HM"] = 0  # Stop homing
                elif turn_angle < 15 or turn_angle > 345:
                    command["motorL"] = 120
                    command["motorR"] = 120
                elif 15 <= turn_angle <= 180:
                    command["motorL"] = 120
                    command["motorR"] = 0
                else:
                    command["motorL"] = 0
                    command["motorR"] = 120

                cmd_str = build_command(command)
                requests.post(COMMAND_URL, data=cmd_str, headers={"Content-Type": "text/plain"}, timeout=2)

        except Exception as e:
            print("[HM] Error:", e)

        time.sleep(0.5)


tc_thread.py/////////////////////////////////////////////////////////////////////////

import time
import math
import json
import os
import requests
import config
import numpy as np
import cv2
import sys

# Path fix for PyInstaller compatibility
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

WAYPOINT_FILE = os.path.join(base_path, "waypoints.json")
COMMAND_URL = f"{config.ESP32_IP}/command"
CAM_URL = f"{config.ESP32_IP}/cam-hi.jpg"

model = config.get_model()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371e3
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_bearing(lat1, lon1, lat2, lon2):
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    y = math.sin(Δλ) * math.cos(φ2)
    x = math.cos(φ1) * math.sin(φ2) - math.sin(φ1) * math.cos(φ2) * math.cos(Δλ)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def tc_loop(build_command, command):
    current_index = 0
    waypoints = []
    servo_angle = 90
    trash_mode = False
    last_seen_time = 0

    last_lat = None
    last_lng = None

    # Load waypoints
    try:
        with open(WAYPOINT_FILE, "r") as f:
            data = json.load(f)
            waypoints = [(k, v) for k, v in data.items() if k != "h"]
            waypoints.sort()
    except Exception as e:
        print("[TC] Failed to load waypoints:", e)
        return

    if not waypoints:
        print("[TC] No waypoints to follow.")
        return

    while True:
        if not config.gui_flags.get("TC", 0):
            time.sleep(2)
            continue

        try:
            parts = config.last_sensor_data.copy()

            # --- Homing trigger check ---
            try:
                if int(parts.get("IR", 0)) == 1:
                    print("[TC] Triggering Homing — Reason: IR Triggered")
                    config.gui_flags["TC"] = 0
                    config.gui_flags["HM"] = 1
                    continue
            except Exception as e:
                print("[TC] IR check error:", e)

            # --- Cache GPS coordinates if present ---
            if "lat" in parts and "lng" in parts:
                try:
                    last_lat = float(parts["lat"])
                    last_lng = float(parts["lng"])
                except:
                    pass

            # --- Proceed if heading is present and GPS has been cached ---
            if "heading" in parts and last_lat is not None and last_lng is not None:
                heading = float(parts["heading"])

                wp_name, (wlat, wlng) = waypoints[current_index]
                config.current_wp_name = wp_name

                dist = haversine(last_lat, last_lng, wlat, wlng)
                bearing = calculate_bearing(last_lat, last_lng, wlat, wlng)
                turn_angle = (bearing - heading + 360) % 360

                # --- Trash Detection Mode ---
                trash_list = list(config.detected_trash)

                if trash_list:
                    config.detected_trash.clear()
                    trash_mode = True
                    last_seen_time = time.time()

                    # Center closest trash
                    frame_center_x = getattr(config, "frame_width", 320) // 2
                    frame_center_y = getattr(config, "frame_height", 240) // 2

                    closest = min(trash_list, key=lambda t: abs(t[0] - frame_center_x))
                    cx, cy, w, h, label = closest

                    centered = False
                    if cx < frame_center_x - 20:
                        command["motorL"] = 0
                        command["motorR"] = 120
                    elif cx > frame_center_x + 20:
                        command["motorL"] = 120
                        command["motorR"] = 0
                    else:
                        centered = True

                    # Servo vertical tracking
                    error = frame_center_y - cy
                    adjustment = max(-15, min(15, error * 0.5))
                    servo_angle += adjustment
                    servo_angle = max(60, min(80, servo_angle))
                    command["servo"] = int(servo_angle)

                    screen_height = getattr(config, "frame_height", 240)
                    if centered and servo_angle <= 68:
                        command["motorL"] = 120
                        command["motorR"] = 120
                        command["e"] = 1
                    else:
                        command["e"] = 0

                elif trash_mode and time.time() - last_seen_time > 5:
                    print("[TC] Lost trash — resuming waypoint navigation")
                    trash_mode = False
                    command["e"] = 0

                # --- Navigation when not in trash mode ---
                if not trash_mode:
                    print(f"[TC] WP:{wp_name} Dist:{dist:.1f}m Turn:{turn_angle:.1f}°")

                    if dist < 5:
                        print(f"[TC] Reached {wp_name}")
                        current_index = (current_index + 1) % len(waypoints)
                        continue

                    speed = 120
                    if turn_angle < 15 or turn_angle > 345:
                        command["motorL"] = speed
                        command["motorR"] = speed
                    elif 15 <= turn_angle <= 180:
                        command["motorL"] = speed
                        command["motorR"] = 0
                    else:
                        command["motorL"] = 0
                        command["motorR"] = speed

                cmd_str = build_command(command)
                requests.post(COMMAND_URL, data=cmd_str, headers={"Content-Type": "text/plain"}, timeout=2)

        except Exception as e:
            print("[TC] Error:", e)

        time.sleep(0.5)
