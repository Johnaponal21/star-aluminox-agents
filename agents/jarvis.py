"""JARVIS - El Orquestador. Recibe, clasifica y deriva."""
import json
from openai import OpenAI
from config import settings
from services.redis_bus import bus

client = OpenAI(api_key=settings.openai_api_key)

JARVIS_SYSTEM_PROMPT = """Eres JARVIS, el coordinador inteligente de Star Aluminox, empresa de equipos de cocina industrial remanufacturados en Colombia.

TU TRABAJO:
1. Analizar el mensaje del cliente y clasificar su INTENCION.
2. Detectar si es una emergencia, reclamo o algo que requiere humano.
3. Asignar el agente correcto.

INTENCIONES POSIBLES:
- consulta_stock: Pregunta si tienen un equipo, disponibilidad, modelos.
- consulta_precio: Pregunta cuanto cuesta, negociacion.
- duda_garantia: Pregunta sobre garantia, reparaciones, soporte.
- duda_estado: Pregunta si esta como nuevo, condicion del equipo, fotos.
- venta_equipo: Cliente quiere vender su equipo usado (trade-in).
- instalacion: Pregunta por instalacion, tecnicos, dimensiones.
- reclamo: Queja, devolucion, equipo fallo.
- saludo_general: Solo saluda, no dice que quiere.
- despedida: Se despide, agradece.
- otro: No encaja en las anteriores.

REGLAS:
- Si detectas palabras como ""reclamo"", ""devolver"", ""no funciona"", ""estafa"", ""denuncia"" -> intencion = ""reclamo_urgente"" y requiere_humano = true.
- Si el cliente pregunta por un equipo especifico (freidora, horno, plancha, etc.) -> intencion = ""consulta_stock"".
- Siempre responde en JSON valido.

FORMATO DE RESPUESTA (JSON obligatorio):
{
    ""intencion"": ""consulta_stock"",
    ""confianza"": 0.95,
    ""equipo_mencionado"": ""freidora"",
    ""urgencia"": ""normal"",
    ""requiere_humano"": false,
    ""resumen"": ""Cliente pregunta si hay freidoras disponibles"",
    ""agente_recomendado"": ""vendedor""
}
"""

class JarvisAgent:
    def __init__(self):
        self.name = ""JARVIS""
    
    def analizar(self, mensaje: str, telefono: str, historial: list) -> dict:
        messages = [
            {""role"": ""system"", ""content"": JARVIS_SYSTEM_PROMPT},
            {""role"": ""user"", ""content"": ""Mensaje del cliente ("" + telefono + ""): "" + mensaje}
        ]
        
        if historial:
            contexto = ""\nHistorial reciente:\n""
            for msg in historial[-5:]:
                contexto += ""- "" + msg[""role""] + "": "" + msg[""content""] + ""\n""
            messages.append({""role"": ""user"", ""content"": contexto})
        
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.2,
            response_format={""type"": ""json_object""}
        )
        
        resultado = json.loads(response.choices[0].message.content)
        
        bus.publish(""jarvis.analisis"", {
            ""telefono"": telefono,
            ""intencion"": resultado.get(""intencion""),
            ""confianza"": resultado.get(""confianza""),
            ""requiere_humano"": resultado.get(""requiere_humano"", False)
        })
        
        return resultado
    
    def generar_saludo(self, nombre_cliente: str = """") -> str:
        nombre = "" "" + nombre_cliente if nombre_cliente else """"
        return ""Hola"" + nombre + ""! Bienvenido a Star Aluminox. Somos especialistas en equipos de cocina industrial remanufacturados con garantia real. En que puedo ayudarte hoy?""

jarvis = JarvisAgent()
