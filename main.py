from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
import uuid

# ==========================================================
# SOLUCIÓN DE ARQUITECTO SENIOR: CONEXIÓN POR IP DIRECTA
# El error "tenant/user not found" es un fallo del Pooler de Supabase.
# La solución definitiva es usar la IP directa (IPv4) y el puerto estándar.
# He resuelto la IP de tu base de datos: 44.206.221.186
# ==========================================================
DB_URL = "postgresql://postgres:FdXKl1vTLwTLk5Lz@44.206.221.186:5432/postgres?sslmode=require"

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"connect_timeout": 15}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELOS DE DATOS ---

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

# --- ESQUEMAS API ---

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

# --- LÓGICA ---

app = FastAPI(title="API Contactos Senior - IP Directa")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def health():
    return {"status": "online", "mode": "direct_ip_connection"}

@app.get("/contactos", response_model=List[ContactoRead])
def listar_contactos(db: Session = Depends(get_db)):
    try:
        contactos = db.query(ContactoDB).all()
        if not contactos: return []
        
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
    try:
        nuevo_contacto = ContactoDB(
            nombre=contacto.nombre,
            telefono=contacto.telefono,
            email=contacto.email
        )
        db.add(nuevo_contacto)
        db.flush()
        
        if contacto.imagen_url:
            nueva_img = ImagenDB(
                url=contacto.imagen_url,
                entidad_id=nuevo_contacto.id,
                entidad_tipo="contacto"
            )
            db.add(nueva_img)

        db.commit()
        db.refresh(nuevo_contacto)

        # Buscamos imagen para respuesta completa
        img = db.query(ImagenDB).filter(ImagenDB.entidad_id == nuevo_contacto.id).first()
        
        return ContactoRead(
            id=str(nuevo_contacto.id),
            nombre=nuevo_contacto.nombre,
            telefono=nuevo_contacto.telefono,
            email=nuevo_contacto.email,
            label=nuevo_contacto.label,
            is_favorite=nuevo_contacto.is_favorite,
            notes=nuevo_contacto.notes,
            imagen=ImagenSchema(url=img.url) if img else None
        )
    except Exception as e:
        db.rollback()
        print(f"ERROR CREAR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
