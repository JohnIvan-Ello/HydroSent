# 🌊 HydroSent: AI-Integrated Autonomous Surface Vessel
**Advanced Aquatic Robotics | Edge AI | Environmental IoT**

HydroSent is a next-generation autonomous floating robot designed for high-efficiency aquatic waste collection. Unlike traditional methods, HydroSent utilizes a specialized **Conveyor-Belt System** and an **ESP32-S3 AI Camera** to detect, target, and retrieve floating debris in real-time. This project represents a complete integration of mechanical engineering, embedded C++, and Python-based computer vision.

---

## 🚀 Technical Upgrades
* **ESP32-S3 AI Integration:** High-speed camera processing for real-time trash detection using optimized neural network weights.
* **Conveyor-Belt Mechanism:** A high-torque collection system controlled via specialized relays, replacing standard scooping methods for continuous operation.
* **Dual-Controller Logic:** Utilizes an Arduino Nano for low-level sensor/motor management and an ESP32-S3 for high-level data streaming.
* **Geospatial Precision:** Integrated GPS and Compass modules for autonomous waypoint navigation and geofencing.

---

## 🛠️ The Technical Stack
| Layer | Technologies & Components |
| **Firmware** | C++ (Arduino), Python (AI Processing) |
| **AI Core** | PyTorch, YOLO-based Object Detection, Custom Datasets |
| **Hardware** | ESP32-S3, Arduino Nano, NEO-6M GPS, HMC5883L Compass |
| **Mechanical** | Conveyor-Belt Assembly, Solar-Charge Management, Dual Propulsion |

---

## 📂 Repository Structure
This project is organized into a modular pipeline for easy hardware-software synchronization:

* **`/firmware`**: Master Arduino logic (`.ino`) and Python AI scripts (`main.py`).
* **`/hardware`**: 3D CAD models, custom PCB layouts, and circuit schematics.
* **`/software`**: Desktop Control Dashboard (`main7.exe`) and real-time telemetry logs.
* **`/documentation`**: Detailed User Manuals, BOM (Bill of Materials), and AI training results.

---

## ⚙️ Engineering Design & Logic
### 1. Autonomous Navigation
The system calculates the shortest path between user-defined GPS waypoints. The **HMC5883L Compass** ensures the vessel maintains a steady heading even in moving water, while **FC-51 IR Sensors** prevent collisions with obstacles.

### 2. AI Training & Perception
The HydroSent model was trained on a specific dataset of aquatic waste. We utilized **Confusion Matrices** and **F1-Curves** to validate detection accuracy before deploying the model to the ESP32-S3 hardware.

### 3. Sustainable Power
The system is self-charging via a solar array. A **PWM Solar Charge Panel** regulates the flow to a Sealed Lead-Acid battery, ensuring the high-current conveyor motor doesn't interfere with the sensitive logic controllers.

---

## 🧪 Quality Assurance (QA)
HydroSent was subjected to a rigorous QA pipeline:
* **Load Testing:** Verified conveyor-belt torque under various weight loads.
* **Connectivity Stress Test:** Tested Wi-Fi telemetry stability at distances up to [X] meters.
* **Environmental Validation:** Accuracy testing of AI detection in high-glare and low-light water conditions.

---
**Developed by John Ivan Ello**
*Technical Artist & Robotics Developer*
