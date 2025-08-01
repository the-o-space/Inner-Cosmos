"""Statistics and tracking endpoints."""
import uuid
import hashlib
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.future import select
from sqlalchemy import text
from ..schemas import HeartbeatRequest
from ..models import Visitor, Session
from ..database import LocalSession
from ..services import compute_stats
import httpx

router = APIRouter()

async def get_geo(ip: str) -> dict | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://ipapi.co/{ip}/json/")
            resp.raise_for_status()
            data = resp.json()
            if 'error' in data:
                return None
            return {
                'country_code': data.get('country_code'),
                'region': data.get('region'),
                'city': data.get('city'),
            }
    except Exception:
        return None

@router.post("/heartbeat")
async def heartbeat(
    request: Request, 
    body: HeartbeatRequest, 
    response: Response
):
    """Track visitor activity and manage sessions."""
    cookie_id = request.cookies.get('visitor_id')
    ip = request.client.host if request.client else '127.0.0.1'
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()
    now = datetime.utcnow()

    async with LocalSession() as db:
        if not cookie_id:
            cookie_id = str(uuid.uuid4())
            response.set_cookie(
                key='visitor_id', 
                value=cookie_id, 
                httponly=True, 
                samesite='strict', 
                max_age=31536000  # 1 year
            )
            visitor = Visitor(
                cookie_id=cookie_id, 
                ip_hash=ip_hash, 
                created_at=now, 
                last_seen_at=now
            )
            geo = await get_geo(ip)
            if geo:
                visitor.country_code = geo['country_code']
                visitor.region = geo['region']
                visitor.city = geo['city']
            db.add(visitor)
            await db.commit()
            await db.refresh(visitor)
        else:
            result = await db.execute(
                select(Visitor).filter_by(cookie_id=cookie_id)
            )
            visitor = result.scalar_one_or_none()
            if not visitor:
                visitor = Visitor(
                    cookie_id=cookie_id, 
                    ip_hash=ip_hash, 
                    created_at=now, 
                    last_seen_at=now
                )
                geo = await get_geo(ip)
                if geo:
                    visitor.country_code = geo['country_code']
                    visitor.region = geo['region']
                    visitor.city = geo['city']
                db.add(visitor)
                await db.commit()
                await db.refresh(visitor)
            elif visitor.ip_hash != ip_hash:
                # IP changed, update
                visitor.ip_hash = ip_hash
                geo = await get_geo(ip)
                if geo:
                    visitor.country_code = geo['country_code']
                    visitor.region = geo['region']
                    visitor.city = geo['city']
            visitor.last_seen_at = now
            await db.commit()

        # Check for active session
        result = await db.execute(
            select(Session).filter_by(visitor_id=visitor.id, is_active=True)
        )
        sess = result.scalar_one_or_none()

        if sess:
            sess.last_heartbeat = now
            sess.action_count += 1
            await db.commit()
            # Return session info for scheduler to handle timeout
            return {
                'status': 'ok', 
                'session_id': sess.id,
                'visitor_id': visitor.id
            }
        else:
            sess = Session(
                visitor_id=visitor.id, 
                start_time=now, 
                last_heartbeat=now, 
                action_count=1
            )
            db.add(sess)
            await db.commit()
            await db.refresh(sess)
            return {
                'status': 'ok', 
                'session_id': sess.id,
                'visitor_id': visitor.id
            }


@router.get("/")
async def get_stats():
    """Get current statistics."""
    return await compute_stats() 

@router.post("/query")
async def query_sql(request: Request):
    """Execute a read-only SQL query (SELECT only) and return results."""
    data = await request.json()
    sql = data.get("sql")
    if not isinstance(sql, str):
        return {"error": "Invalid SQL parameter"}
    if not sql.strip().lower().startswith("select"):
        return {"error": "Only SELECT queries are allowed"}
    try:
        async with LocalSession() as db:
            result = await db.execute(text(sql))
            rows = result.fetchall()
            columns = result.keys()
            results = [dict(zip(columns, row)) for row in rows]
        return {"results": results}
    except Exception as e:
        return {"error": f"Query execution failed: {str(e)}"} 