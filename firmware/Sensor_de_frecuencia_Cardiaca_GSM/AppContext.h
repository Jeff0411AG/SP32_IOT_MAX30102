#pragma once

#include <Arduino.h>
#include <EEPROM.h>
#include <Wire.h>
#include <esp_system.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include "MAX30105.h"
#include "heartRate.h"

extern int Lectura;
extern float Voltaje;
extern byte Porcent;

extern const byte MaxNumeros;
extern String Numeros[];
extern byte CantidadDeNumeros;
extern byte Var;
extern String Temporal;
extern String EnvioMen;
extern byte Milis;
extern String AdminNumero;
extern bool AdminConfigurado;
extern unsigned long UltimaRevisionSMS;
extern const unsigned long IntervaloRevisionSMS;
extern const int TamanoMaxTelefono;
extern const int EEPROMSize;
extern const uint32_t ConfigMagic;
extern const String CodigoReset;

extern const uint8_t i2c_Address;
extern const int SCREEN_WIDTH;
extern const int SCREEN_HEIGHT;
extern const int OLED_RESET;
extern Adafruit_SH1106G display;

extern MAX30105 particleSensor;

extern const byte RATE_SIZE;
extern byte rates[];
extern byte rateSpot;
extern long lastBeat;
extern float beatsPerMinute;
extern int beatAvg;

extern double avered;
extern double aveir;
extern double sumirrms;
extern double sumredrms;
extern double SpO2;
extern double ESpO2;
extern double FSpO2;
extern double frate;
extern int i;
extern int Num;
extern const long FINGER_ON;
extern const double MINIMUM_SPO2;

extern long irValue;
extern const byte LimitLectIncorr;
extern byte LectIncorr;
extern const byte LimitLectCorrec;
extern byte LectCorrec;
extern const byte Buzzer;
extern bool Mensaje;
extern bool ConteoActivo;
extern byte ConteoRegresivo;
extern unsigned long UltimoTickConteo;
extern bool InicioOperativoNotificado;
extern unsigned long UltimoLatidoVisual;
extern int CSQActual;
extern byte BarrasGSM;
extern unsigned long UltimaRevisionGSM;
extern const unsigned long IntervaloRevisionGSM;
extern bool DisplayDisponible;
extern unsigned long UltimaActualizacionPantalla;
extern const unsigned long IntervaloPantalla;
extern unsigned long InicioBootMillis;
extern const unsigned long RetardoNotificacionInicio;
extern byte IntentosNotificacionInicio;
extern const byte MaxIntentosNotificacionInicio;
extern long IrBase;
extern long UmbralDedoActual;
extern unsigned long InicioLecturaDedo;
extern const unsigned long TimeoutLecturaDedo;
extern bool SensorEnCalibracion;
extern bool EnvioBiometricoArmado;
extern unsigned long UltimoEnvioBiometrico;
extern const unsigned long EnfriamientoEnvioBiometrico;
extern bool ModoPresentacion;
extern const byte ConteoRegresivoNormal;
extern const byte ConteoRegresivoPresentacion;
extern const byte LecturasEstablesNormal;
extern const byte LecturasEstablesPresentacion;
extern const unsigned long TimeoutLecturaNormal;
extern const unsigned long TimeoutLecturaPresentacion;
extern const int SpO2MuestrasNormal;
extern const int SpO2MuestrasPresentacion;

const char *TextoMotivoReset(esp_reset_reason_t motivo);
