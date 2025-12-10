"""
Router de consultas catastrales
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from auth.dependencies import get_current_active_user, check_query_limit
import models
import schemas

router = APIRouter(prefix="/api/catastro", tags=["Catastro"])


@router.post("/query", response_model=schemas.QueryResponse)
async def create_query(
    query_data: schemas.QueryCreate,
    current_user: models.User = Depends(check_query_limit),
    db: Session = Depends(get_db)
):
    """
    Crear nueva consulta catastral
    
    Este endpoint:
    1. Verifica que el usuario tenga consultas disponibles
    2. Crea el registro de consulta
    3. Incrementa el contador de consultas usadas
    4. Devuelve la información de la consulta
    
    NOTA: La lógica de procesamiento real (llamar al sistema catastral original)
    debe implementarse aquí o en un worker asíncrono.
    """
    
    # Crear consulta
    new_query = models.Query(
        user_id=current_user.id,
        referencia_catastral=query_data.referencia_catastral,
        has_climate_data=False,  # Se actualizará después del procesamiento
        has_socioeconomic_data=False,
        has_pdf=False
    )
    
    db.add(new_query)
    
    # Incrementar contador de consultas
    subscription = db.query(models.Subscription).filter(
        models.Subscription.user_id == current_user.id
    ).first()
    
    subscription.queries_used += 1
    
    db.commit()
    db.refresh(new_query)
    
    # TODO: Aquí se debe llamar al sistema catastral original
    # para procesar la referencia y generar los datos
    # Esto puede hacerse de forma asíncrona con Celery o similar
    
    return new_query


@router.get("/queries", response_model=List[schemas.QueryResponse])
async def get_my_queries(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Obtener historial de consultas del usuario"""
    
    queries = db.query(models.Query).filter(
        models.Query.user_id == current_user.id
    ).order_by(models.Query.created_at.desc()).offset(skip).limit(limit).all()
    
    return queries


@router.get("/queries/{query_id}", response_model=schemas.QueryResponse)
async def get_query(
    query_id: str,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Obtener detalles de una consulta específica"""
    
    query = db.query(models.Query).filter(
        models.Query.id == query_id,
        models.Query.user_id == current_user.id
    ).first()
    
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    
    return query


@router.get("/stats")
async def get_stats(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Obtener estadísticas de uso del usuario"""
    
    subscription = db.query(models.Subscription).filter(
        models.Subscription.user_id == current_user.id
    ).first()
    
    total_queries = db.query(models.Query).filter(
        models.Query.user_id == current_user.id
    ).count()
    
    return {
        "total_queries": total_queries,
        "queries_used_this_period": subscription.queries_used if subscription else 0,
        "queries_limit": subscription.queries_limit if subscription else 0,
        "queries_remaining": (subscription.queries_limit - subscription.queries_used) if subscription else 0,
        "plan_type": subscription.plan_type if subscription else None
    }
