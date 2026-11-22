// // Do Nothing Code

// #include <Arduino.h>

// int pumpPin = 9;
// int valvePin = 8;

// void setup() {
//   pinMode(pumpPin, OUTPUT);
//   pinMode(valvePin, OUTPUT);
//   digitalWrite(pumpPin, LOW);
//   digitalWrite(valvePin, LOW);
// }

// void loop() {
//   // does nothing — pump and valve stay off
// }

#include <Arduino.h>

int pumpPin = 9;
int valvePin = 8;

void inflate() {
  digitalWrite(valvePin, HIGH);
  digitalWrite(pumpPin, HIGH);
}

void stopAll() {
  digitalWrite(pumpPin, LOW);
  digitalWrite(valvePin, LOW);
}

void setup() {
  pinMode(pumpPin, OUTPUT);
  pinMode(valvePin, OUTPUT);
}

void loop() {
  inflate();
  delay(3000);
  stopAll();
  delay(3000);
}

