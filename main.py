from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
import uuid

# ==========================================================
# CONFIGURACIÓN DE CONEXIÓN DEFINITIVA
# Usamos el Pooler de Supabase (Puerto 6543) para máxima compatibilidad con Render
# ==========================================================
# URL Definitiva para Render (Evita error de red IPv6 y error de Tenant)
DB_URL = "postgresql://postgres:FdXKl1vTLwTLk5Lz@db.oxbbcoyiskgtxliytgax.supabase.co:5432/postgres?sslmode=require"

engine = create_engine(
    DB_URL, 
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELOS DE BASE DE DATOS ---
class ContactoDB(Base):
    __tablename__ = "contactos"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=False)
    email = Column(String)
    label = Column(String, default="Mobile")
    is_favorite = Column(Boolean, default=False)
    notes = Column(Text)

class ImagenDB(Base):
    __tablename__ = "imagenes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(String, nullable=False)
    entidad_id = Column(UUID(as_uuid=True), nullable=False)
    entidad_tipo = Column(String, nullable=False)

# --- ESQUEMAS PARA LA API (PYDANTIC) ---
class ImagenSchema(BaseModel):
    url: str

class ContactoRead(BaseModel):
    id: str
    nombre: str
    telefono: str
    email: Optional[str]
    label: str
    is_favorite: bool
    notes: Optional[str]
    imagen: Optional[ImagenSchema] = None
    class Config:
        from_attributes = True

class ContactoCreate(BaseModel):
    nombre: str
    telefono: str
    email: Optional[str] = None
    imagen_url: Optional[str] = None

# --- INICIALIZACIÓN ---
app = FastAPI(title="API Contactos Profesional")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "online", "message": "Backend listo para recibir contactos"}

@app.get("/contactos", response_model=List[ContactoRead])
def listar_contactos(db: Session = Depends(get_db)):
    try:
        contactos = db.query(ContactoDB).all()
        if not contactos:
            return []
        
        resultado = []
        for c in contactos:
            # Buscar imagen en la tabla polimórfica
            img = db.query(ImagenDB).filter(
                ImagenDB.entidad_id == c.id,
                ImagenDB.entidad_tipo == "contacto"
            ).first()
            
            resultado.append(ContactoRead(
                id=str(c.id),
                nombre=c.nombre,
                telefono=c.telefono,
                email=c.email,
                label=c.label,
                is_favorite=c.is_favorite,
                notes=c.notes,
                imagen=ImagenSchema(url=img.url) if img else None
            ))
        return resultado
    except Exception as e:
        print(f"ERROR EN LISTAR: {str(e)}")
        return [] # Retornamos lista vacía para evitar error 500 en la app

@app.post("/contactos", response_model=ContactoRead)
def crear_contacto(contacto: ContactoCreate, db: Session = Depends(get_db)):
    try:
        # 1. Crear Contacto
        nuevo_contacto = ContactoDB(
            nombre=contacto.nombre,
            telefono=contacto.telefono,
            email=contacto.email
        )
        db.add(nuevo_contacto)
        db.commit()
        db.refresh(nuevo_contacto)
        
        # 2. Crear Imagen Polimórfica (si existe URL)
        imagen_obj = None
        if contacto.imagen_url:
            nueva_img = ImagenDB(
                url=contacto.imagen_url,
                entidad_id=nuevo_contacto.id,
                entidad_tipo="contacto"
            )
            db.add(nueva_img)
            db.commit()
            imagen_obj = ImagenSchema(url=nueva_img.url)

        return ContactoRead(
            id=str(nuevo_contacto.id),
            nombre=nuevo_contacto.nombre,
            telefono=nuevo_contacto.telefono,
            email=nuevo_contacto.email,
            label=nuevo_contacto.label,
            is_favorite=nuevo_contacto.is_favorite,
            notes=nuevo_contacto.notes,
            imagen=imagen_obj
        )
    except Exception as e:
        db.rollback()
        print(f"ERROR EN CREAR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
