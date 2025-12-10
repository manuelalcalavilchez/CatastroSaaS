"""
Router de consultas catastrales
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import io
import zipfile
import json
from datetime import datetime

from fastapi.responses import StreamingResponse

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
        kml_content=query_data.kml_content,  # Guardar KML si se proporciona
        has_climate_data=False,
        has_socioeconomic_data=False,
        has_pdf=False,
        has_wms_maps=False
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


def _create_pdf_bytes(query):
    """Genera un PDF elegante y completo para una consulta con mapas WMS si disponibles.

    Usa ReportLab Platypus para crear un documento con portada, tabla de resumen,
    sección de metadatos, mapas WMS y datos de afección.
    """
    try:
        # Imports locales
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            PageBreak,
            Preformatted,
            Image as RLImage,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        import base64

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'Title', parent=styles['Heading1'], alignment=1, fontSize=18, spaceAfter=8
        )
        h2 = ParagraphStyle('H2', parent=styles['Heading2'], spaceBefore=12, spaceAfter=6)
        normal = styles['Normal']
        code_style = ParagraphStyle('Code', parent=styles.get('Code', styles['Normal']), fontName='Courier', fontSize=8)

        elems = []

        # Portada
        elems.append(Paragraph('Catastro SaaS', title_style))
        elems.append(Spacer(1, 6))
        elems.append(Paragraph('<b>Informe Catastral Integrado</b>', styles['Title']))
        elems.append(Spacer(1, 8))
        elems.append(Paragraph(f'<b>Referencia:</b> {query.referencia_catastral}', normal))
        elems.append(Paragraph(f'<b>Fecha:</b> {query.created_at}', normal))
        if hasattr(query, 'user') and getattr(query, 'user') is not None:
            elems.append(Paragraph(f'<b>Usuario:</b> {getattr(query.user, "email", "-")}', normal))
        elems.append(Spacer(1, 12))
        elems.append(Paragraph('Este documento contiene el resumen de la consulta catastral, datos de afección, mapas WMS y archivos generados por el sistema.', normal))
        elems.append(PageBreak())

        # Resumen y tabla de metadatos
        elems.append(Paragraph('Resumen de la Consulta', h2))
        summary_data = [
            ['Campo', 'Valor'],
            ['Referencia', query.referencia_catastral],
            ['ID', query.id],
            ['Fecha de creación', str(query.created_at)],
            ['PDF generado', 'Sí' if query.has_pdf else 'No'],
            ['Mapas WMS', 'Sí' if query.has_wms_maps else 'No'],
            ['Datos climáticos', 'Sí' if query.has_climate_data else 'No'],
            ['Datos socioeconómicos', 'Sí' if query.has_socioeconomic_data else 'No'],
        ]

        table = Table(summary_data, colWidths=[60 * mm, 90 * mm], hAlign='LEFT')
        table.setStyle(
            TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ])
        )
        elems.append(table)
        elems.append(Spacer(1, 10))

        # Datos de afección WMS si están disponibles
        if query.wms_affection_data:
            try:
                affection_data = json.loads(query.wms_affection_data)
                elems.append(PageBreak())
                elems.append(Paragraph('Análisis de Afección - Datos WMS', h2))
                
                for capa, datos in affection_data.items():
                    if isinstance(datos, dict) and 'error' not in datos:
                        elems.append(Paragraph(f'Capa: {capa}', styles['Heading3']))
                        affection_table_data = [['Umbral', 'Porcentaje Afectado']]
                        for umbral_key, porcentaje in datos.items():
                            affection_table_data.append([umbral_key.replace('umbral_', 'Umbral '), f'{porcentaje}%'])
                        
                        aff_table = Table(affection_table_data, colWidths=[50 * mm, 100 * mm])
                        aff_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8f4f8')),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 6),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                        ]))
                        elems.append(aff_table)
                        elems.append(Spacer(1, 8))
            except Exception:
                pass

        # Metadatos JSON (preformatted)
        elems.append(Paragraph('Metadatos (detallado)', h2))
        meta = {
            'id': query.id,
            'referencia_catastral': query.referencia_catastral,
            'has_pdf': bool(query.has_pdf),
            'has_wms_maps': bool(query.has_wms_maps),
            'has_climate_data': bool(query.has_climate_data),
            'has_socioeconomic_data': bool(query.has_socioeconomic_data),
            'created_at': str(query.created_at),
        }
        meta_pre = Preformatted(json.dumps(meta, indent=2, ensure_ascii=False), code_style)
        elems.append(meta_pre)
        elems.append(Spacer(1, 8))

        # Secciones detalladas
        elems.append(Paragraph('Datos Catastrales', h2))
        elems.append(Paragraph('Resumen de información catastral: coordenadas, superficie, usos del suelo, parcelas y referencias espaciales.', normal))
        elems.append(Spacer(1, 6))

        if query.has_wms_maps:
            elems.append(Paragraph('Mapas WMS', h2))
            elems.append(Paragraph('Incluye capas temáticas: Montes Públicos, Red Natura 2000, Vías Pecuarias, superpuestas sobre ortofoto IGN.', normal))
            elems.append(Spacer(1, 6))

        if query.has_climate_data:
            elems.append(Paragraph('Datos Climáticos (AEMET)', h2))
            elems.append(Paragraph('Indicadores meteorológicos: temperatura media, precipitación anual, datos de estaciones cercanas.', normal))
            elems.append(Spacer(1, 6))

        if query.has_socioeconomic_data:
            elems.append(Paragraph('Datos Socioeconómicos (INE)', h2))
            elems.append(Paragraph('Información agregada por municipio: población, renta media, indicadores socioeconómicos.', normal))
            elems.append(Spacer(1, 6))

        elems.append(Paragraph('Archivos incluidos en el paquete', h2))
        elems.append(Paragraph('Informe PDF (este documento), imágenes de mapas (si procede), KML/GML, datos JSON de afección y metadatos.', normal))

        # Pie de página
        elems.append(Spacer(1, 18))
        elems.append(Paragraph('Generado por Catastro SaaS • Análisis Catastral Integral', styles['Normal']))

        # Construir documento con páginas
        def _header_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica-Bold', 9)
            canvas.drawString(20 * mm, A4[1] - 15 * mm, 'Catastro SaaS')
            canvas.setFont('Helvetica', 8)
            page_text = f'Página {doc.page}'
            canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, page_text)
            canvas.restoreState()

        doc.build(elems, onFirstPage=_header_footer, onLaterPages=_header_footer)
        buffer.seek(0)
        return buffer.read()
    except Exception as e:
        # Fallback
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            c.setFont('Helvetica-Bold', 14)
            c.drawString(40, 800, 'Informe Catastral - (fallback)')
            c.setFont('Helvetica', 10)
            c.drawString(40, 780, f'Referencia: {query.referencia_catastral}')
            c.drawString(40, 765, f'Creado: {query.created_at}')
            c.showPage()
            c.save()
            buf.seek(0)
            return buf.read()
        except Exception:
            return f"Referencia: {query.referencia_catastral}\nCreado: {query.created_at}\n".encode('utf-8')


def _create_zip_for_queries(queries):
    """Crea un ZIP con PDFs mejorados, metadatos, imágenes WMS y datos de afección."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for q in queries:
            folder = f"{q.referencia_catastral}_{q.id}"
            
            # Metadatos principales
            meta = {
                'id': q.id,
                'referencia_catastral': q.referencia_catastral,
                'has_pdf': bool(q.has_pdf),
                'has_wms_maps': bool(q.has_wms_maps),
                'has_climate_data': bool(q.has_climate_data),
                'has_socioeconomic_data': bool(q.has_socioeconomic_data),
                'created_at': str(q.created_at)
            }
            z.writestr(f"{folder}/metadata.json", json.dumps(meta, indent=2, default=str))

            # PDF report enriquecido
            pdf_bytes = _create_pdf_bytes(q)
            z.writestr(f"{folder}/report.pdf", pdf_bytes)

            # Datos de afección WMS si existen
            if q.wms_affection_data:
                z.writestr(f"{folder}/affection_data.json", q.wms_affection_data)

            # KML si existe
            if q.kml_content:
                z.writestr(f"{folder}/geometry.kml", q.kml_content)

            # Datos climáticos
            if q.has_climate_data:
                z.writestr(f"{folder}/AEMET_climate_data.txt", "Datos climáticos AEMET (por implementar en procesamiento real)")

            # Datos socioeconómicos
            if q.has_socioeconomic_data:
                z.writestr(f"{folder}/INE_socioeconomic_data.txt", "Datos socioeconómicos INE (por implementar en procesamiento real)")

            # Nota informativa
            z.writestr(f"{folder}/README.txt", 
                f"""Consulta Catastral - {q.referencia_catastral}
Fecha: {q.created_at}
Usuario: {q.user.email if q.user else 'desconocido'}

Contenido del paquete:
- report.pdf: Informe PDF completo con análisis de afección y mapas
- metadata.json: Información estructurada de la consulta
- affection_data.json: Porcentajes de afección por capa WMS (si disponible)
- geometry.kml: Geometría de la parcela en formato KML (si disponible)
- Archivos de datos temáticos: AEMET, INE, etc.

Para más información, visite: https://example.com
""")

    buf.seek(0)
    return buf.getvalue()

@router.get("/queries/{query_id}/download")
async def download_query_zip(
    query_id: str,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generar y devolver un ZIP con los archivos asociados a una consulta"""
    query = db.query(models.Query).filter(models.Query.id == query_id, models.Query.user_id == current_user.id).first()
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    zip_bytes = _create_zip_for_queries([query])
    filename = f"catastro_query_{query.referencia_catastral}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.zip"
    return StreamingResponse(io.BytesIO(zip_bytes), media_type='application/zip', headers={
        'Content-Disposition': f'attachment; filename="{filename}"'
    })


@router.post("/queries/export")
async def export_queries(
    ids: List[str],
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Exportar múltiples consultas (lista de ids) como un ZIP descargable"""
    queries = db.query(models.Query).filter(models.Query.id.in_(ids), models.Query.user_id == current_user.id).all()
    if not queries:
        raise HTTPException(status_code=404, detail="No queries found for given ids")

    zip_bytes = _create_zip_for_queries(queries)
    filename = f"catastro_queries_export_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.zip"
    return StreamingResponse(io.BytesIO(zip_bytes), media_type='application/zip', headers={
        'Content-Disposition': f'attachment; filename="{filename}"'
    })


@router.post("/query/{query_id}/process-wms")
async def process_query_with_wms(
    query_id: str,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Procesa una consulta existente: obtiene KML, descarga mapas WMS y calcula afecciones.
    Requiere que la consulta tenga contenido KML.
    """
    try:
        from services.wms_service import procesar_consulta_catastral
        
        query = db.query(models.Query).filter(
            models.Query.id == query_id,
            models.Query.user_id == current_user.id
        ).first()
        
        if not query:
            raise HTTPException(status_code=404, detail="Query not found")
        
        if not query.kml_content:
            raise HTTPException(status_code=400, detail="Query does not contain KML content")
        
        # Procesar: parsear KML, descargar WMS, calcular afecciones
        resultados = procesar_consulta_catastral(query.kml_content, query.referencia_catastral)
        
        # Actualizar query con resultados
        query.has_wms_maps = True
        query.wms_affection_data = json.dumps(resultados.get('capas', {}), default=str, ensure_ascii=False)
        
        db.commit()
        db.refresh(query)
        
        return {
            "status": "success",
            "query_id": query.id,
            "referencia": query.referencia_catastral,
            "capas_procesadas": list(resultados.get('capas', {}).keys()),
            "has_wms_maps": True
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing WMS: {str(e)}")

