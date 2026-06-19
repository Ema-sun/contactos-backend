from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
import uuid

# ==========================================================
# ARQUITECTURA DE CONEXIÓN SENIOR - SOLUCIÓN DEFINITIVA
# El problema "Network is unreachable" ocurre por la resolución IPv6 de Render.
# Usamos el Pooler de Supabase en el puerto 5432 con el usuario compuesto.
# ==========================================================
DB_URL = "postgresql://postgres.oxbbcoyiskgtxliytgax:FdXKl1vTLwTLk5Lz@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"

# Configuramos el engine con timeouts y pings de salud para evitar desconexiones
engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={
        "connect_timeout": 10,
        "application_name": "contactos_app"
    }
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELOS DE DATOS (Relacional Polimórfico) ---

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

# --- ESQUEMAS DE API (Clean JSON) ---

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

# --- LÓGICA DE NEGOCIO ---

app = FastAPI(title="Contactos API Senior")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def health():
    return {"status": "online", "engine": "PostgreSQL + SQLAlchemy"}

@app.get("/contactos", response_model=List[ContactoRead])
def listar_contactos(db: Session = Depends(get_db)):
    """
    Realiza un JOIN lógico para recuperar contactos e imágenes polimórficas.
    """
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
        print(f"ERROR LISTAR: {str(e)}")
        return []

@app.post("/contactos", response_model=ContactoRead)
def crear_contacto(contacto: ContactoCreate, db: Session = Depends(get_db)):
    """
    Inserción Transaccional ATÓMICA (ACID).
    Garantiza que el contacto y su imagen se guarden juntos o nada se guarde.
    """
    try:
        # Inicia transacción
        nuevo_contacto = ContactoDB(
            nombre=contacto.nombre,
            telefono=contacto.telefono,
            email=contacto.email
        )
        db.add(nuevo_contacto)
        db.flush() # Genera el ID para la relación polimórfica
        
        imagen_obj = None
        if contacto.imagen_url:
            nueva_img = ImagenDB(
                url=contacto.imagen_url,
                entidad_id=nuevo_contacto.id,
                entidad_tipo="contacto"
            )
            db.add(nueva_img)
            imagen_obj = ImagenSchema(url=nueva_img.url)

        db.commit() # Fin de la transacción
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
        print(f"ERROR CREAR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
