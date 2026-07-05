#pragma once

#include "AppContext.h"

int ExtraeCSQ(String respuesta);
byte ConvierteCSQABarras(int csq);
void DibujaBarrasGSM(int x, int y);
void DibujaCabeceraEstado();
void DibujaPanelDato(int x, int y, int w, int h, const char *titulo, String valor, bool resaltar);
String TextoEstadoMedicion(bool dedoPresente);
bool PuedeArmarNuevoEnvioBiometrico();
void RenderPantallaPrincipal(bool dedoPresente, bool forzar = false);
