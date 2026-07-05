#pragma once

#include "AppContext.h"

void ReportaMotivoReset();
void ReiniciaConteoMedicion();
void ActualizaUmbralDedo();
void CalibraSensorSinDedo(long lecturaIR);
bool DedoDetectado(long lecturaIR);

void LimpiaContactos();
void ReiniciaEstadoFabrica(bool guardarEnEEPROM);
void ActualizaCantidadDeNumeros();
void EscribeCadenaEEPROM(int direccion, String valor, int longitudMaxima);
String LeeCadenaEEPROM(int direccion, int longitudMaxima);
void GuardaConfiguracion();
void CargaConfiguracion();
void ActualizaBateria();

String LimpiaTelefono(String numero);
String ExtraeCampoEntreComillas(String texto, byte indiceCampo);
int ExtraeIndiceSMS(String cabecera);
String NormalizaComando(String comando);
String NormalizaTelefonoGuardado(String numero);
bool EsTelefonoValido(String numero);
int BuscaContacto(String numero);
int BuscaEspacioLibreContacto();
String ResumenContactos();
bool EsAdministrador(String numero);
bool EsNumeroAutorizado(String numero);
bool EsComandoValido(String comando);
