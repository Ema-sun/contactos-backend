from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Boolean, Text, ForeignKey, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
import uuid

# Configuración de Base de Datos (Supabase)
# Reemplaza con tus credenciales si es necesario
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:FdXKl1vTLwTLk5Lz@db.oxbbcoyiskgtxliytgax.supabase.co:5432/postgres"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Modelos de Base de Datos (SQLAlchemy) ---

class ContactoDB(Base):
    __tablename__ = "contactos"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=False)
    email = Column(String)
    label = Column(String, default="Mobile")
    is_favorite = Column(Boolean, default=False)
    notes = Column(Text)

class ImagenDB(Base):
    __tablename__ = "imagenes"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, nullable=False)
    entidad_id = Column(String, nullable=False)
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
    id: str
    nombre: str
    telefono: str
    email: Optional[str]
    label: str
    is_favorite: bool
    notes: Optional[str]
    imagen: Optional[ImagenSchema]

    class Config:
        orm_mode = True

# --- Dependencia de Sesión ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="API de Contactos Profesional")

# --- Endpoints ---

@app.post("/contactos", response_model=ContactoRead)
def crear_contacto(contacto: ContactoCreate, db: Session = Depends(get_db)):
    """
    Inserción Transaccional: Se guarda el contacto y su imagen polimórfica.
    Si algo falla, el rollback automático de la sesión evita datos huérfanos.
    """
    try:
        # 1. Crear el objeto Contacto
        nuevo_contacto = ContactoDB(
            id=str(uuid.uuid4()),
            nombre=contacto.nombre,
            telefono=contacto.telefono,
            email=contacto.email,
            label=contacto.label,
            is_favorite=contacto.is_favorite,
            notes=contacto.notes
        )
        db.add(nuevo_contacto)

        # 2. Si hay imagen, crear el registro polimórfico
        imagen_obj = None
        if contacto.imagen_url:
            nueva_imagen = ImagenDB(
                id=str(uuid.uuid4()),
                url=contacto.imagen_url,
                entidad_id=nuevo_contacto.id,
                entidad_tipo="contacto"
            )
            db.add(nueva_imagen)
            imagen_obj = ImagenSchema(url=nueva_imagen.url)

        # 3. Commit de la transacción
        db.commit()
        db.refresh(nuevo_contacto)

        # Retornar objeto estructurado
        return ContactoRead(
            **nuevo_contacto.__dict__,
            imagen=imagen_obj
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error transaccional: {str(e)}")

@app.get("/contactos", response_model=List[ContactoRead])
def listar_contactos(db: Session = Depends(get_db)):
    """
    JOIN Lógico: Obtiene contactos e imágenes polimórficas de forma eficiente.
    """
    contactos = db.query(ContactoDB).all()
    resultado = []

    for c in contactos:
        # Buscar la imagen correspondiente en la tabla polimórfica
        img = db.query(ImagenDB).filter(
            ImagenDB.entidad_id == c.id,
            ImagenDB.entidad_tipo == "contacto"
        ).first()

        resultado.append(ContactoRead(
            **c.__dict__,
            imagen=ImagenSchema(url=img.url) if img else None
        ))

    return resultado

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
