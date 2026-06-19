from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Boolean, Text, ForeignKey, select
from sqlalchemy.dialects.postgresql import UUID # IMPORTANTE: Usar UUID nativo
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
import uuid

# Configuración de Base de Datos (Supabase)
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:FdXKl1vTLwTLk5Lz@db.oxbbcoyiskgtxliytgax.supabase.co:5432/postgres"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Modelos de Base de Datos (SQLAlchemy) ---

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

# --- Esquemas Pydantic para API ---

class ImagenSchema(BaseModel):
    url: str

class ContactoCreate(BaseModel):
    nombre: str
    telefono: str
    email: Optional[str] = None
    label: Optional[str] = "Mobile"
    is_favorite: Optional[bool] = False
    notes: Optional[str] = ""
    imagen_url: Optional[str] = None

class ContactoRead(BaseModel):
    id: str # El ID lo enviamos como string al móvil
    nombre: str
    telefono: str
    email: Optional[str]
    label: str
    is_favorite: bool
    notes: Optional[str]
    imagen: Optional[ImagenSchema] = None

    class Config:
        from_attributes = True # Actualizado para Pydantic v2 (según tu log de Render)

# --- Dependencia de Sesión ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="API de Contactos Profesional")

@app.get("/")
def read_root():
    return {"status": "online", "message": "Backend de Contactos listo"}

@app.post("/contactos", response_model=ContactoRead)
def crear_contacto(contacto: ContactoCreate, db: Session = Depends(get_db)):
    try:
        # 1. Crear el objeto Contacto con UUID real
        nuevo_contacto = ContactoDB(
            nombre=contacto.nombre,
            telefono=contacto.telefono,
            email=contacto.email,
            label=contacto.label,
            is_favorite=contacto.is_favorite,
            notes=contacto.notes
        )
        db.add(nuevo_contacto)
        db.flush() # Obtener el ID generado por la DB
        
        # 2. Si hay imagen, crear el registro polimórfico
        imagen_obj = None
        if contacto.imagen_url:
            nueva_imagen = ImagenDB(
                url=contacto.imagen_url,
                entidad_id=nuevo_contacto.id,
                entidad_tipo="contacto"
            )
            db.add(nueva_imagen)
            imagen_obj = ImagenSchema(url=nueva_imagen.url)

        db.commit()
        db.refresh(nuevo_contacto)

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
        print(f"CRITICAL ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en base de datos: {str(e)}")

@app.get("/contactos", response_model=List[ContactoRead])
def listar_contactos(db: Session = Depends(get_db)):
    try:
        contactos = db.query(ContactoDB).all()
        resultado = []
        for c in contactos:
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
        print(f"GET ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
