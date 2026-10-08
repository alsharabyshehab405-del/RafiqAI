import hashlib,io,os,uuid,zipfile
from pathlib import Path
from ..config import settings

ALLOWED={"application/pdf","text/plain","text/csv","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","image/jpeg","image/png","image/webp"}
def object_key(user_id,filename): return f"users/{user_id}/{uuid.uuid4().hex}-{Path(filename).name[:120]}"
def sha256(data:bytes): return hashlib.sha256(data).hexdigest()
def validate_upload(filename,content_type,data):
    if len(data)>settings.max_file_bytes: raise ValueError("file too large")
    if content_type not in ALLOWED: raise ValueError("unsupported file type")
    lower=filename.lower()
    if lower.endswith(".pdf") and not data.startswith(b"%PDF"): raise ValueError("invalid pdf")
    if lower.endswith((".jpg",".jpeg")) and not data.startswith(b"\xff\xd8\xff"): raise ValueError("invalid image")
    if lower.endswith(".png") and not data.startswith(b"\x89PNG"): raise ValueError("invalid image")
    if lower.endswith((".docx",".xlsx")):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if len(z.infolist()) > 10000 or sum(i.file_size for i in z.infolist()) > settings.max_file_uncompressed_bytes: raise ValueError("archive expands beyond safety limit")
                if not z.testzip() is None: raise ValueError("invalid office archive")
        except zipfile.BadZipFile: raise ValueError("invalid office archive")
    return True

def scan_bytes(data):
    if not settings.clamav_url: return True
    import httpx
    try:
        r=httpx.post(settings.clamav_url.rstrip("/")+"/scan",content=data,timeout=30)
        r.raise_for_status(); return r.json().get("clean") is True
    except Exception: raise ValueError("virus scan unavailable")

def put_object(key,data,content_type):
    if not settings.s3_bucket: raise RuntimeError("object storage is not configured")
    import boto3
    client=boto3.client("s3",region_name=settings.s3_region,endpoint_url=settings.s3_endpoint_url or None,aws_access_key_id=settings.s3_access_key or None,aws_secret_access_key=settings.s3_secret_key or None)
    client.put_object(Bucket=settings.s3_bucket,Key=key,Body=data,ContentType=content_type,ServerSideEncryption="AES256")

def delete_object(key):
    if not settings.s3_bucket:return
    import boto3
    client=boto3.client("s3",region_name=settings.s3_region,endpoint_url=settings.s3_endpoint_url or None,aws_access_key_id=settings.s3_access_key or None,aws_secret_access_key=settings.s3_secret_key or None)
    client.delete_object(Bucket=settings.s3_bucket,Key=key)

def signed_url(key,expires=900):
    if not settings.s3_bucket:return None
    import boto3
    client=boto3.client("s3",region_name=settings.s3_region,endpoint_url=settings.s3_endpoint_url or None,aws_access_key_id=settings.s3_access_key or None,aws_secret_access_key=settings.s3_secret_key or None)
    return client.generate_presigned_url("get_object",Params={"Bucket":settings.s3_bucket,"Key":key},ExpiresIn=expires)

def extract_text(filename,content_type,data):
    if content_type=="application/pdf":
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)[:100000]
    if content_type=="application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)[:100000]
    if content_type.startswith("text/") or content_type == "text/csv":
        return data.decode("utf-8","replace")[:100000]
    if content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        from openpyxl import load_workbook
        wb=load_workbook(io.BytesIO(data),read_only=True,data_only=True)
        rows=[]
        for ws in wb.worksheets:
            rows.append(f"# Sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True): rows.append("\t".join("" if v is None else str(v) for v in row))
        return "\n".join(rows)[:100000]
    return ""
