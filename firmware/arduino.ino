#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_HMC5883_U.h>
#include <SoftwareSerial.h>

  int motorL = 0, motorR = 0, servo = 0, e = 0;
int ir = 0;                     // final flag to send to ESP
unsigned long seenStart = 0;   // when trash was first seen
bool trashDetected = false;
unsigned long lastOnTime = 0;
bool relayShouldBeOn = false;
// Rightt Motor
const int ENA = 9;
const int IN1 = 5;
const int IN2 = 6;
#define SERVO_PIN 11  

// Left Motor
const int ENB = 10;
const int IN3 = 7;
const int IN4 = 8;
#define ESP_RX A3
#define ESP_TX A2
SoftwareSerial espSerial(ESP_RX, ESP_TX);  // RX = from ESP, TX = to ESP

const int volPin = A0;
const int solpin = A1;

const int irpin = 4;
int relpin=12;
Adafruit_HMC5883_Unified mag = Adafruit_HMC5883_Unified(12345);

void setup() {
    pinMode(SERVO_PIN, OUTPUT);

    pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);

  pinMode(solpin, OUTPUT);
pinMode(relpin,OUTPUT);
digitalWrite(relpin,HIGH);
  pinMode(ENB, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  Serial.begin(9600);         
  espSerial.begin(4800);      

  if (!mag.begin()) {
    Serial.println("Compass init failed!");
    while (1);
  }

  pinMode(irpin, INPUT);
  delay(200);
}

void loop() {
  // --- Handle incoming serial commands ---
  if (espSerial.available()) {
    String request = espSerial.readStringUntil('\n');
    request.trim();
    Serial.println("Raw Command: " + request);

    if (request == "credentials") {
      espSerial.println("isaiahwifi");
      delay(100);
      espSerial.println("asd1234b");
    }
    else if (request == "REQ") {
      // --- Read battery ---
      int rawVol = analogRead(volPin);
      float voltage = rawVol * 0.01955;
      int percentage = constrain((voltage - 9.0) * 27.777, 0, 100);

      // Control solar relay
      digitalWrite(solpin, (percentage < 99) ? LOW : HIGH);

      // --- IR sensor ---
      bool current = digitalRead(irpin);
      if (current == LOW) {
        if (!trashDetected) {
          seenStart = millis();
          trashDetected = true;
        } else if (millis() - seenStart >= 5000) {
          ir = 1;
        }
      } else {
        trashDetected = false;
        ir = 0;
      }

      // --- Compass heading ---
      sensors_event_t event;
      mag.getEvent(&event);
      float heading = atan2(event.magnetic.y, event.magnetic.x) + 0.047;
      heading = fmod(heading + 2 * PI, 2 * PI);
      float headingDeg = heading * 180.0 / PI;

      // --- Send back sensor data ---
      String data = "battery:" + String(percentage) +
                    ",IR:" + String(ir) +
                    ",heading:" + String(headingDeg, 1);
      espSerial.println(data);
      delay(20);
    }

    else if (request.indexOf("motorL:") >= 0 || 
             request.indexOf("motorR:") >= 0 || 
             request.indexOf("servo:") >= 0 || 
             request.indexOf("e:") >= 0) {

      int lIdx = request.indexOf("motorL:");
      int rIdx = request.indexOf("motorR:");
      int sIdx = request.indexOf("servo:");
      int eIdx = request.indexOf("e:");

      if (lIdx >= 0) {
        int endIdx = request.indexOf(",", lIdx);
        if (endIdx == -1) endIdx = request.length();
        motorL = request.substring(lIdx + 7, endIdx).toInt();
      }

      if (rIdx >= 0) {
        int endIdx = request.indexOf(",", rIdx);
        if (endIdx == -1) endIdx = request.length();
        motorR = request.substring(rIdx + 7, endIdx).toInt();
      }

      if (sIdx >= 0) {
        int endIdx = request.indexOf(",", sIdx);
        if (endIdx == -1) endIdx = request.length();
        servo = request.substring(sIdx + 6, endIdx).toInt();
      }

      if (eIdx >= 0) {
        int endIdx = request.indexOf(",", eIdx);
        if (endIdx == -1) endIdx = request.length();
        e = request.substring(eIdx + 2, endIdx).toInt();
      }

      Serial.print("motorL: "); Serial.println(motorL);
      Serial.print("motorR: "); Serial.println(motorR);
      Serial.print("servo: ");  Serial.println(servo);
      Serial.print("e: ");      Serial.println(e);

      // Relay trigger handling
      if (e == 1) {
        relayShouldBeOn = true;
        lastOnTime = millis();
      }
    }
    else {
      if (request.length() > 0) {
        Serial.println("Ignored message: " + request);
      }
    }
  }

  // --- Apply motor control even without new command ---
  mL(motorL);
  mR(motorR);

  // --- Apply servo control ---
  if (servo > 60) {
    //either these three lines or line 170
    //servo=servo+28;
    //servo=map(servo,78,138,78,100)//change of range here we deducted looking up by 38 degrees
    //writeServo(servo);  // Adjust as needed
    writeServo(servo + 28);  // Adjust as needed
  
    delay(20);
  }

  // --- Keep relay ON for 5 seconds after e=1 ---
  if (relayShouldBeOn) {
    digitalWrite(relpin, LOW);  // Relay ON
    if (millis() - lastOnTime >= 5000) {
      relayShouldBeOn = false;
    }
  } else {
    digitalWrite(relpin, HIGH);  // Relay OFF
  }
}

// ======== Motor Control Functions ========

// Set right motor speed (signed: +forward, -reverse)
void mR(int speed) {
  speed = constrain(speed, -255, 255);
  if (speed >= 0) {
    digitalWrite(IN1, HIGH);
    digitalWrite(IN2, LOW);
  } else {
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, HIGH);
    speed = -speed;
  }
  analogWrite(ENA, speed);
}

// Set left motor speed (signed)
void mL(int speed) {
  speed = constrain(speed, -255, 255);
  if (speed >= 0) {
    digitalWrite(IN3, HIGH);
    digitalWrite(IN4, LOW);
  } else {
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, HIGH);
    speed = -speed;
  }
  analogWrite(ENB, speed);
}


// Manually send PWM pulse for given angle
void writeServo(int angle) {
  int pulseWidth = map(angle, 0, 180, 544, 2400); // µs
  digitalWrite(SERVO_PIN, HIGH);
  delayMicroseconds(pulseWidth);
  digitalWrite(SERVO_PIN, LOW);
  delay(20); // 20ms total cycle (standard servo refresh rate)
}
