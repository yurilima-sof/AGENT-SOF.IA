from pydantic import BaseModel

class RagIngestRequest(BaseModel):
    id_grupo: str
    mensagem: str

class RagIngestResponse(BaseModel):
    status: str
    mensagem: str
