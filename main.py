"""
STAR ALUMINOX AGENTS - Sistema Multi-Agente para Ventas
FastAPI app con webhooks de WhatsApp Business API
"""
import os
import json
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from config import settings
from database import init_db, get_db, Conversacion, Equipo
from services.redis_bus import bus
from services.whatsapp import whatsapp
from agents.jarvis import jarvis
from agents.vendedor import vendedor
from agents.brain import brain

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(""Iniciando Star Aluminox Agents..."")
    init_db()
    print(""Base de datos inicializada"")
    yield
    print(""Apagando agentes..."")

app = FastAPI(
    title=""Star Aluminox Agents"",
    description=""Sistema multi-agente de IA para ventas de equipos remanufacturados"",
    version=""1.0.0"",
    lifespan=lifespan
)

@app.get(""/"")
async def root():
    return {
        ""status"": ""online"",
        ""business"": settings.business_name,
        ""agents"": [""JARVIS"", ""BRAIN"", ""Vendedor_1""],
        ""version"": ""1.0.0""
    }

@app.get(""/health"")
async def health():
    return {""status"": ""ok"", ""timestamp"": str(datetime.utcnow())}

@app.get(""/webhook/whatsapp"")
async def verify_webhook(hub_mode: str = """", hub_verify_token: str = """", hub_challenge: str = """"):
    if hub_mode == ""subscribe"" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail=""Verification failed"")

@app.post(""/webhook/whatsapp"")
async def receive_whatsapp_message(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    body = await request.json()
    try:
        entry = body.get(""entry"", [{}])[0]
        changes = entry.get(""changes"", [{}])[0]
        value = changes.get(""value"", {})
        
        if ""messages"" not in value:
            return {""status"": ""ignored"", ""reason"": ""not a message""}
        
        message = value[""messages""][0]
        from_number = message.get(""from"")
        msg_type = message.get(""type"")
        
        if msg_type != ""text"":
            return {""status"": ""ignored"", ""reason"": ""non-text message""}
        
        text = message[""text""][""body""]
        print(""Mensaje de "" + from_number + "": "" + text[:50] + ""..."")
        
        background_tasks.add_task(procesar_mensaje, from_number, text, db)
        return {""status"": ""received""}
        
    except Exception as e:
        print(""Error procesando webhook: "" + str(e))
        return {""status"": ""error"", ""detail"": str(e)}

async def procesar_mensaje(telefono: str, mensaje: str, db: Session):
    try:
        historial = bus.get_conversation(telefono)
        analisis = jarvis.analizar(mensaje, telefono, historial)
        print(""JARVIS: "" + analisis[""intencion""] + "" (confianza: "" + str(analisis[""confianza""]) + "")"")
        
        if analisis.get(""requiere_humano"", False):
            print(""ALERTA HUMANA - Tel: "" + telefono)
            return
        
        if analisis[""intencion""] == ""saludo_general"" and not historial:
            respuesta = jarvis.generar_saludo()
        else:
            respuesta = vendedor.responder(
                mensaje_cliente=mensaje,
                telefono=telefono,
                intencion=analisis[""intencion""],
                historial=historial
            )
        
        enviado = await vendedor.enviar_respuesta(telefono, respuesta)
        print(""Respuesta enviada: "" + str(enviado))
        
        conv = Conversacion(
            cliente_telefono=telefono,
            canal=""whatsapp"",
            agente_asignado=""vendedor_1"",
            mensaje_cliente=mensaje,
            respuesta_agente=respuesta,
            intencion=analisis[""intencion""],
            objecion=analisis.get(""objecion_detectada"")
        )
        db.add(conv)
        db.commit()
        
        bus.publish(""sistema.venta_pipeline"", {
            ""telefono"": telefono,
            ""intencion"": analisis[""intencion""],
            ""timestamp"": str(datetime.utcnow())
        })
        
    except Exception as e:
        print(""Error en pipeline: "" + str(e))
        try:
            await whatsapp.send_text(telefono, ""Disculpa, tuve un problema tecnico. Un asesor humano te contactara en minutos."")
        except:
            pass

@app.get(""/admin/conversaciones"")
async def listar_conversaciones(db: Session = Depends(get_db), limite: int = 50):
    convs = db.query(Conversacion).order_by(Conversacion.created_at.desc()).limit(limite).all()
    return [{
        ""id"": c.id,
        ""telefono"": c.cliente_telefono,
        ""intencion"": c.intencion,
        ""mensaje"": c.mensaje_cliente[:100],
        ""respuesta"": (c.respuesta_agente[:100] if c.respuesta_agente else None),
        ""venta"": c.venta_cerrada,
        ""fecha"": str(c.created_at)
    } for c in convs]

@app.get(""/admin/inventario"")
async def listar_inventario(db: Session = Depends(get_db)):
    equipos = db.query(Equipo).all()
    return [{
        ""id"": e.id,
        ""nombre"": e.nombre,
        ""categoria"": e.categoria,
        ""precio"": e.precio,
        ""estado"": e.estado,
        ""condicion"": e.condicion,
        ""garantia"": e.garantia_meses
    } for e in equipos]

@app.post(""/admin/inventario"")
async def agregar_equipo(nombre: str, categoria: str, precio: float, condicion: str = ""remanufacturado"", garantia: int = 6, descripcion: str = """", db: Session = Depends(get_db)):
    equipo = Equipo(nombre=nombre, categoria=categoria, precio=precio, condicion=condicion, garantia_meses=garantia, descripcion=descripcion)
    db.add(equipo)
    db.commit()
    db.refresh(equipo)
    return {""status"": ""ok"", ""equipo_id"": equipo.id}

@app.post(""/admin/marcar-venta"")
async def marcar_venta(conversacion_id: int, monto: float, db: Session = Depends(get_db)):
    conv = db.query(Conversacion).filter(Conversacion.id == conversacion_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail=""Conversacion no encontrada"")
    conv.venta_cerrada = True
    conv.monto_venta = monto
    db.commit()
    return {""status"": ""venta registrada"", ""monto"": monto}

@app.post(""/admin/brain/analizar"")
async def ejecutar_analisis_brain():
    resultado = brain.analizar_dia()
    return {""status"": ""ok"", ""analisis"": resultado}

@app.get(""/admin/brain/reporte"")
async def reporte_matutino():
    reporte = brain.generar_reporte_morning()
    return {""reporte"": reporte}

@app.post(""/admin/seed-inventario"")
async def seed_inventario(db: Session = Depends(get_db)):
    equipos_seed = [
        Equipo(nombre=""Freidora Industrial 20L"", categoria=""freidora"", precio=1200000, precio_original=2500000, condicion=""remanufacturado"", garantia_meses=6, descripcion=""Freidora de acero inoxidable, termostato nuevo, resistencias revisadas. Incluye canastillas.""),
        Equipo(nombre=""Plancha Industrial 90cm"", categoria=""plancha"", precio=850000, precio_original=1800000, condicion=""remanufacturado"", garantia_meses=6, descripcion=""Plancha a gas con 3 quemadores, superficie cromada, incluye regulador.""),
        Equipo(nombre=""Horno Convector 4 Bandejas"", categoria=""horno"", precio=3200000, precio_original=6500000, condicion=""remanufacturado"", garantia_meses=12, descripcion=""Horno convector electrico, ventilador nuevo, resistencias cambiadas, control digital calibrado.""),
        Equipo(nombre=""Licuadora Industrial 4L"", categoria=""licuadora"", precio=450000, precio_original=900000, condicion=""remanufacturado"", garantia_meses=3, descripcion=""Licuadora de alta velocidad, vaso de policarbonato nuevo, motor revisado.""),
        Equipo(nombre=""Estufa Industrial 4 Puestos"", categoria=""estufa"", precio=1500000, precio_original=3200000, condicion=""remanufacturado"", garantia_meses=6, descripcion=""Estufa a gas con plancha y freidora integrada, quemadores nuevos, estructura reforzada.""),
    ]
    for eq in equipos_seed:
        db.add(eq)
    db.commit()
    return {""status"": ""seed completado"", ""equipos_agregados"": len(equipos_seed)}

if __name__ == ""__main__"":
    import uvicorn
    port = int(os.environ.get(""PORT"", 8000))
    uvicorn.run(app, host=""0.0.0.0"", port=port)
