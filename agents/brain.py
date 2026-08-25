"""BRAIN - El analista estrategico. No habla con clientes. Piensa y mejora."""
import json
from datetime import datetime, timedelta
from openai import OpenAI
from sqlalchemy.orm import Session
from sqlalchemy import func
from config import settings
from database import get_db, Conversacion, Equipo, LeccionAprendida
from services.redis_bus import bus

client = OpenAI(api_key=settings.openai_api_key)

BRAIN_SYSTEM_PROMPT = """Eres BRAIN, el analista estrategico de Star Aluminox. No hablas con clientes.

AREAS DE ANALISIS:
1. OBJECIONES: Detecta patrones de por que se pierden ventas.
2. PRECIOS: Identifica si los precios estan bien calibrados.
3. INVENTARIO: Detecta equipos estancados o de alta rotacion.
4. SCRIPTS: Genera nuevas respuestas para objeciones frecuentes.

FORMATO DE RESPUESTA (JSON):
{
    ""resumen_ejecutivo"": ""texto corto"",
    ""objeciones_detectadas"": [{""objecion"": ""precio_alto"", ""frecuencia"": 5, ""solucion_propuesta"": ""texto""}],
    ""recomendaciones_inventario"": [{""equipo"": ""freidora"", ""accion"": ""bajar_precio_10"", ""razon"": ""texto""}],
    ""nuevas_lecciones"": [{""categoria"": ""objecion_precio"", ""descripcion"": ""..."", ""solucion"": ""...""}],
    ""alertas"": [""texto""]
}
"""

class BrainAgent:
    def __init__(self):
        self.name = ""BRAIN""
        self.db = next(get_db())
    
    def analizar_dia(self) -> dict:
        ayer = datetime.utcnow() - timedelta(days=1)
        conversaciones = self.db.query(Conversacion).filter(Conversacion.created_at >= ayer).all()
        
        if not conversaciones:
            return {""resumen_ejecutivo"": ""Sin conversaciones en las ultimas 24 horas.""}
        
        datos = {
            ""total_conversaciones"": len(conversaciones),
            ""ventas_cerradas"": sum(1 for c in conversaciones if c.venta_cerrada),
            ""monto_total"": sum(c.monto_venta or 0 for c in conversaciones),
            ""objeciones"": [c.objecion for c in conversaciones if c.objecion],
            ""intenciones"": [c.intencion for c in conversaciones if c.intencion],
            ""muestra_conversaciones"": []
        }
        
        for c in conversaciones[:20]:
            datos[""muestra_conversaciones""].append({
                ""cliente"": c.cliente_telefono,
                ""intencion"": c.intencion,
                ""mensaje"": c.mensaje_cliente[:200],
                ""respuesta"": (c.respuesta_agente[:200] if c.respuesta_agente else """"),
                ""venta"": c.venta_cerrada,
                ""objecion"": c.objecion
            })
        
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {""role"": ""system"", ""content"": BRAIN_SYSTEM_PROMPT},
                {""role"": ""user"", ""content"": ""Analiza estos datos del dia:\n"" + json.dumps(datos, ensure_ascii=False, indent=2)}
            ],
            temperature=0.3,
            response_format={""type"": ""json_object""}
        )
        
        resultado = json.loads(response.choices[0].message.content)
        
        for leccion in resultado.get(""nuevas_lecciones"", []):
            self._guardar_leccion(leccion)
        
        bus.publish(""brain.analisis"", {
            ""fecha"": str(datetime.utcnow()),
            ""resumen"": resultado.get(""resumen_ejecutivo""),
            ""ventas"": datos[""ventas_cerradas""],
            ""total_conversaciones"": datos[""total_conversaciones""]
        })
        
        return resultado
    
    def _guardar_leccion(self, leccion: dict):
        existente = self.db.query(LeccionAprendida).filter(
            LeccionAprendida.categoria == leccion.get(""categoria""),
            LeccionAprendida.descripcion == leccion.get(""descripcion"")
        ).first()
        
        if existente:
            existente.frecuencia += 1
            existente.solucion = leccion.get(""solucion"", existente.solucion)
            existente.updated_at = datetime.utcnow()
        else:
            nueva = LeccionAprendida(
                categoria=leccion.get(""categoria"", ""general""),
                descripcion=leccion.get(""descripcion"", """"),
                solucion=leccion.get(""solucion"", """"),
                frecuencia=1
            )
            self.db.add(nueva)
        
        self.db.commit()
    
    def generar_reporte_morning(self) -> str:
        analisis = self.analizar_dia()
        reporte = ""Reporte Matutino Star Aluminox\n\n"" + analisis.get(""resumen_ejecutivo"", ""Sin resumen"")
        
        reporte += ""\n\nObjeciones detectadas:\n""
        for obj in analisis.get(""objeciones_detectadas"", []):
            reporte += ""\n- "" + obj.get(""objecion"") + "" ("" + str(obj.get(""frecuencia"")) + "" veces)\n  Solucion: "" + obj.get(""solucion_propuesta"", ""N/A"")
        
        reporte += ""\n\nRecomendaciones de inventario:\n""
        for rec in analisis.get(""recomendaciones_inventario"", []):
            reporte += ""- "" + rec.get(""equipo"") + "": "" + rec.get(""accion"") + "" - "" + rec.get(""razon"") + ""\n""
        
        if analisis.get(""alertas""):
            reporte += ""\nAlertas:\n""
            for alerta in analisis[""alertas""]:
                reporte += ""- "" + alerta + ""\n""
        
        return reporte

brain = BrainAgent()
