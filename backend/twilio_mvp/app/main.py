from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Form, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from .config_store import (
    append_audit_event,
    is_admin,
    is_authorized,
    load_config,
    load_state,
    normalize_phone,
    recipients,
    save_config,
    save_state,
)
from .settings import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_TEST_MODE


app = FastAPI(title="ESP32 Twilio MVP")


class StartupPayload(BaseModel):
    device_id: str
    message: str
    battery: int
    wifi_rssi: int | None = None


class AlertPayload(BaseModel):
    device_id: str
    status: str
    bpm: int
    spo2: int
    battery: int
    message: str


class DebugCommandPayload(BaseModel):
    from_number: str
    body: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def twilio_client() -> Client:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_FROM_NUMBER:
        raise HTTPException(status_code=500, detail="Twilio no configurado en el backend.")
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def twiml_message(body: str) -> str:
    response = MessagingResponse()
    response.message(body)
    return str(response)


def audit_event(kind: str, payload: dict[str, Any]) -> None:
    append_audit_event(
        {
            "kind": kind,
            "at": now_iso(),
            **payload,
        }
    )


def send_sms(to_number: str, body: str) -> dict[str, Any]:
    normalized_to = normalize_phone(to_number)
    client = twilio_client()
    try:
        message = client.messages.create(
            from_=TWILIO_FROM_NUMBER,
            to=normalized_to,
            body=body,
        )
        result = {
            "ok": True,
            "to": normalized_to,
            "sid": message.sid,
            "status": getattr(message, "status", None),
            "test_mode": TWILIO_TEST_MODE,
        }
        audit_event("sms_outbound", result | {"body": body})
        return result
    except Exception as exc:
        result = {
            "ok": False,
            "to": normalized_to,
            "error": str(exc),
            "test_mode": TWILIO_TEST_MODE,
        }
        audit_event("sms_outbound_error", result | {"body": body})
        return result


def validate_device(device_id: str, token: str | None) -> dict[str, Any]:
    config = load_config()
    if device_id != config.get("device_id"):
        raise HTTPException(status_code=403, detail="device_id no autorizado")
    if token != config.get("device_token"):
        raise HTTPException(status_code=403, detail="token no autorizado")
    return config


def format_status(config: dict[str, Any], state: dict[str, Any]) -> str:
    last_alert = state.get("last_alert")
    contacts = recipients(config)
    if last_alert:
        resumen = (
            f"Ultimo estado: {last_alert['status']} | BPM: {last_alert['bpm']} | "
            f"SpO2: {last_alert['spo2']}% | Bat: {last_alert['battery']}%"
        )
    else:
        resumen = "Sin alertas previas registradas"
    return f"[ONLINE] Contactos: {len(contacts)} | {resumen}"


def process_incoming_command(number: str, raw_body: str) -> str:
    config = load_config()
    state = load_state()

    body = raw_body.strip().upper()
    parts = body.split()
    command = parts[0] if parts else ""
    args = parts[1:]

    audit_event(
        "sms_inbound",
        {
            "from": normalize_phone(number),
            "body": raw_body,
            "normalized_body": body,
        },
    )

    if command == "":
        reply = "Comando no valido."
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if not config.get("admin_phone"):
        config["admin_phone"] = normalize_phone(number)
        save_config(config)
        reply = "ADMIN REGISTRADO. Backend listo para recibir comandos."
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if command == "STATUS" or body == "STATUS?":
        if not is_authorized(config, number):
            reply = "Numero no autorizado para este equipo."
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        reply = format_status(config, state)
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if not is_admin(config, number):
        reply = "Comando solo para administrador"
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if command == "ADD":
        if len(args) != 1:
            reply = "Comando invalido. Use: ADD +51XXXXXXXXX"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        new_number = normalize_phone(args[0])
        if new_number in recipients(config):
            reply = f"Numero ya registrado: {new_number}"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        config["contacts"].append(new_number)
        save_config(config)
        reply = f"Numero agregado: {new_number}"
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if command == "DEL":
        if len(args) != 1:
            reply = "Comando invalido. Use: DEL +51XXXXXXXXX"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        target = normalize_phone(args[0])
        if target == normalize_phone(config["admin_phone"]):
            reply = "No se puede eliminar el numero administrador"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        if target not in [normalize_phone(item) for item in config.get("contacts", [])]:
            reply = f"Numero no encontrado: {target}"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        config["contacts"] = [item for item in config["contacts"] if normalize_phone(item) != target]
        save_config(config)
        reply = f"Eliminado: {target}"
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if command == "CAMBIAR":
        if len(args) != 2:
            reply = "Comando invalido. Use: CAMBIAR +51OLD +51NEW"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        old_number = normalize_phone(args[0])
        new_number = normalize_phone(args[1])
        contacts = [normalize_phone(item) for item in config.get("contacts", [])]
        if old_number not in contacts:
            reply = f"Numero no encontrado: {old_number}"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        if new_number in recipients(config):
            reply = f"Numero nuevo ya registrado: {new_number}"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        config["contacts"] = [new_number if normalize_phone(item) == old_number else item for item in config["contacts"]]
        save_config(config)
        reply = f"Numero actualizado: {old_number} -> {new_number}"
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if command == "RESET":
        if len(args) != 1:
            reply = "Comando invalido. Use: RESET 2468"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        if args[0] != config.get("reset_code", "2468"):
            reply = "Codigo RESET incorrecto"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        config["admin_phone"] = ""
        config["contacts"] = []
        save_config(config)
        reply = "RESET OK - Estado de fabrica"
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    reply = "Comando no valido. Use STATUS, ADD, DEL, CAMBIAR o RESET."
    audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
    return reply


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true"}


@app.post("/api/startup")
def startup(
    payload: StartupPayload,
    x_device_token: str | None = Header(default=None),
) -> dict[str, Any]:
    config = validate_device(payload.device_id, x_device_token)
    state = load_state()
    state["last_startup"] = payload.model_dump() | {"received_at": now_iso()}
    save_state(state)

    sent = []
    for target in recipients(config):
        sent.append(send_sms(target, payload.message))

    return {"ok": True, "sent": sent}


@app.post("/api/alert")
def alert(
    payload: AlertPayload,
    x_device_token: str | None = Header(default=None),
) -> dict[str, Any]:
    config = validate_device(payload.device_id, x_device_token)
    state = load_state()
    state["last_alert"] = payload.model_dump() | {"received_at": now_iso()}
    save_state(state)

    sent = []
    for target in recipients(config):
        sent.append(send_sms(target, payload.message))

    return {"ok": True, "sent": sent}


@app.post("/twilio/webhook", response_class=PlainTextResponse)
def twilio_webhook(
    From: str = Form(...),
    Body: str = Form(...),
) -> str:
    return twiml_message(process_incoming_command(From, Body))


@app.post("/debug/command")
def debug_command(payload: DebugCommandPayload) -> dict[str, Any]:
    reply = process_incoming_command(payload.from_number, payload.body)
    state = load_state()
    config = load_config()
    return {
        "ok": True,
        "reply": reply,
        "config": config,
        "audit_tail": state.get("audit_log", [])[-10:],
    }


@app.get("/debug/audit")
def debug_audit() -> dict[str, Any]:
    state = load_state()
    return {
        "ok": True,
        "audit_log": state.get("audit_log", []),
    }
