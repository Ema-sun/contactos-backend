from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
import uuid

# --- CONFIGURACIÓN DE CONEXIÓN DE ALTA ESTABILIDAD ---
# Usamos el modo Transaction Pooler (Puerto 6543) optimizado para Render/Supabase
SQLALCHEMY_DATABASE_URL = "postgresql://postgres.oxbbcoyiskgtxliytgax:FdXKl1vTLwTLk5Lz@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require&prepare_threshold=0"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_size=5,           # Reducimos conexiones para evitar saturación
    max_overflow=10,
    pool_pre_ping=True,    # Verifica si la conexión está viva
    pool_recycle=300,      # Reinicia conexiones viejas
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELOS ---
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

# --- ESQUEMAS ---
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

# --- DEPENDENCIAS ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

@app.get("/")
def health():
    return {"status": "online"}

@app.post("/contactos", response_model=ContactoRead)
def crear_contacto(contacto: ContactoCreate, db: Session = Depends(get_db)):
    try:
        nuevo_contacto = ContactoDB(
            nombre=contacto.nombre,
            telefono=contacto.telefono,
            email=contacto.email,
            label=contacto.label,
            is_favorite=contacto.is_favorite,
            notes=contacto.notes
        )
        db.add(nuevo_contacto)
        db.flush()
        
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
        raise HTTPException(status_code=500, detail=str(e))

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
        raise HTTPException(status_code=500, detail=str(e))
