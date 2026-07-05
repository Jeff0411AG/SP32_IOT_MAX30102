#pragma once

#include "AppContext.h"

String ClasificaSpO2(int spo2);
String ClasificaBPM(int bpm);
String NivelGeneral(int spo2, int bpm);
String RecomendacionClinica(int spo2, int bpm);
String ConstruyeMensajeBiometrico();
String ConstruyeMensajeInicio();

bool SistemaListoParaNotificacionInicio();
void NotificaInicioOperativo();
void ActualizaEstadoGSM(bool forzar);

bool RespuestaGSMContiene(const String &texto);
bool LeeRespuestaGSM(unsigned long timeoutMs, bool detenerEnPrompt = false);
String ExtraeLinea(String texto, int &cursor);
void EnviarSMSA(String numeroDestino, String mensaje);
void BorraSMS(int indiceSMS);
void ProcesaComandoSMS(String numeroRemitente, String comandoSMS);
void RevisaSMSRecibidos();
void EnviaMensaje();
void VaciarBufferGSM();
boolean EnviaYEscucha(String Estring);
boolean EnviaYEscucha(String Estring, unsigned long timeoutMs);
