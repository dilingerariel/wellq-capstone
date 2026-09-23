import logging
from pymongo import MongoClient
from pymongo.database import Database
from app.config import settings

logger = logging.getLogger(__name__)

class MongoDB:
    client: MongoClient = None
    db: Database = None

mongodb = MongoDB()

def connect_to_mongo():
    """Conectar a MongoDB e inicializar índices básicos si es necesario"""
    try:
        logger.info(f"Conectando a MongoDB en {settings.MONGODB_URI}...")
        mongodb.client = MongoClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        mongodb.db = mongodb.client[settings.MONGODB_DB]
        # Validar conexión
        mongodb.client.admin.command('ping')
        logger.info("✅ Conexión a MongoDB establecida exitosamente.")
        
        # Crear índices para la colección clinical_tests
        init_indexes(mongodb.db)
    except Exception as e:
        logger.error(f"❌ Error al conectar a MongoDB: {e}")
        raise e

def close_mongo_connection():
    """Cerrar la conexión a MongoDB"""
    if mongodb.client:
        mongodb.client.close()
        logger.info("Conexión a MongoDB cerrada.")

def get_database() -> Database:
    """Dependency para inyectar la base de datos en endpoints de FastAPI"""
    if mongodb.db is None:
        raise RuntimeError("La base de datos MongoDB no está inicializada.")
    return mongodb.db

def init_indexes(db: Database):
    """Garantizar que existan los índices requeridos"""
    try:
        collection = db.clinical_tests
        collection.create_index([("clinical_test_id", 1)], unique=True)
        collection.create_index([("patient_id", 1), ("test_date", -1), ("created_at", -1)])
        collection.create_index([("patient_id", 1), ("upload.client_upload_id", 1)], unique=True)
        collection.create_index([("upload.upload_id", 1)], unique=True)
        collection.create_index([("case_id", 1), ("test_date", -1)])
        collection.create_index([("appointment_id", 1), ("test_date", -1)])
        collection.create_index([("upload.status", 1), ("updated_at", 1)])
        logger.info("✅ Índices de MongoDB verificados/creados.")
    except Exception as e:
        logger.warning(f"Aviso al crear índices (posiblemente ya existen): {e}")
