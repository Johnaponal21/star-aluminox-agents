"""VENDEDOR - El agente de ventas que habla con clientes."""
import json
from openai import OpenAI
from sqlalchemy.orm import Session
from config import settings
from database import get_db, Equipo, LeccionAprendida
from services.redis_bus import bus
from services.whatsapp import whatsapp

client = OpenAI(api_key=settings.openai_api_key)

VENDEDOR_SYSTEM_PROMPT = """Eres un Vendedor Senior de Star Aluminox en Colombia. Vendes equipos de cocina industrial REMANUFACTURADOS.

QUE ES ""REMANUFACTURADO""?
- Equipos usados que pasaron por revision tecnica completa.
- Se cambian piezas desgastadas, se limpian, se calibran.
- Salen con GARANTIA ESCRITA de 6 meses.
- Ahorran hasta 50% vs comprar nuevo.

TU PERSONALIDAD:
- Colombiano, calido, profesional pero cercano.
- Eres experto en equipos de cocina industrial.
- SIEMPRE destacas la garantia y el ahorro vs nuevo.
- Si no sabes algo, dices ""Dejame confirmar eso con nuestro ingeniero"".

INVENTARIO ACTUAL (se actualiza automaticamente):
{inventario}

LECCIONES APRENDIDAS:
{lecciones}

REGLAS DE VENTA:
1. Nunca inventes precios. Solo usa los precios del inventario actual.
2. Si preguntan por un equipo que NO esta en inventario, di: ""En este momento no tenemos ese modelo, pero me puedes dejar tu numero y te aviso cuando llegue.""
3. Siempre ofrece la garantia como valor agregado principal.
4. Si el cliente dice ""esta caro"", NO bajes el precio de inmediato. Primero muestra valor.
5. Cierra con una pregunta de compromiso: ""Te gustaria que te reserve el equipo con un abono del 10%?""

FORMATO: Responde directamente al cliente. Maximo 3-4 oraciones cortas. No uses listas ni JSON.
"""

class VendedorAgent:
    def __init__(self):
        self.name = ""Vendedor_1""
        self.db = next(get_db())
    
    def _get_inventario_texto(self) -> str:
        equipos = self.db.query(Equipo).filter(Equipo.estado == ""disponible"").all()
        if not equipos:
            return ""No hay equipos disponibles en este momento.""
        texto = ""\n""
        for e in equipos:
            texto += ""- "" + e.nombre + "" ("" + e.condicion + "") - $"" + str(int(e.precio)) + "" COP - Garantia: "" + str(e.garantia_meses) + "" meses\n""
        return texto
    
    def _get_lecciones_texto(self) -> str:
        lecciones = self.db.query(LeccionAprendida).order_by(LeccionAprendida.frecuencia.desc()).limit(10).all()
        if not lecciones:
            return ""Sin lecciones registradas aun.""
        texto = ""\n""
        for l in lecciones:
            texto += ""- ["" + l.categoria + ""] "" + l.descripcion + "" -> Solucion: "" + l.solucion + ""\n""
        return texto
    
    def responder(self, mensaje_cliente: str, telefono: str, intencion: str, historial: list) -> str:
        inventario = self._get_inventario_texto()
        lecciones = self._get_lecciones_texto()
        
        hist_texto = """"
        if historial:
            hist_texto = ""\nHistorial de conversacion:\n""
            for msg in historial[-8:]:
                rol = ""Cliente"" if msg[""role""] == ""user"" else ""Vendedor""
                hist_texto += rol + "": "" + msg[""content""] + ""\n""
        
        system_prompt = VENDEDOR_SYSTEM_PROMPT.format(inventario=inventario, lecciones=lecciones)
        
        messages = [
            {""role"": ""system"", ""content"": system_prompt},
            {""role"": ""user"", ""content"": hist_texto + ""\nIntencion detectada: "" + intencion + ""\nMensaje actual del cliente: "" + mensaje_cliente}
        ]
        
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        respuesta = response.choices[0].message.content.strip()
        
        bus.cache_conversation(telefono, ""user"", mensaje_cliente)
        bus.cache_conversation(telefono, ""assistant"", respuesta)
        
        bus.publish(""vendedor.respuesta"", {
            ""telefono"": telefono,
            ""intencion"": intencion,
            ""respuesta_preview"": respuesta[:100]
        })
        
        return respuesta
    
    async def enviar_respuesta(self, telefono: str, mensaje: str):
        return await whatsapp.send_text(telefono, mensaje)

vendedor = VendedorAgent()
