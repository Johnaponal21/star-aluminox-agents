"""Conexión a PostgreSQL y modelos SQLAlchemy."""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Equipo(Base):
    __tablename__ = "equipos"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    categoria = Column(String(100), nullable=False)
    estado = Column(String(50), default="disponible")
    precio = Column(Float, nullable=False)
    precio_original = Column(Float, nullable=True)
    condicion = Column(String(50), default="remanufacturado")
    descripcion = Column(Text)
    garantia_meses = Column(Integer, default=6)
    imagenes = Column(Text)
    fecha_ingreso = Column(DateTime, default=datetime.utcnow)
    destacado = Column(Boolean, default=False)

class Conversacion(Base):
    __tablename__ = "conversaciones"
    
    id = Column(Integer, primary_key=True, index=True)
    cliente_telefono = Column(String(50), index=True)
    cliente_nombre = Column(String(200))
    canal = Column(String(50))
    agente_asignado = Column(String(50))
    mensaje_cliente = Column(Text)
    respuesta_agente = Column(Text)
    intencion = Column(String(100))
    venta_cerrada = Column(Boolean, default=False)
    monto_venta = Column(Float, nullable=True)
    objecion = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class InventarioLog(Base):
    __tablename__ = "inventario_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    equipo_id = Column(Integer)
    accion = Column(String(50))
    detalle = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class LeccionAprendida(Base):
    __tablename__ = "lecciones_aprendidas"
    
    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(String(100))
    descripcion = Column(Text)
    solucion = Column(Text)
    frecuencia = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
