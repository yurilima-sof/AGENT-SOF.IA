import time
import hmac
import hashlib
import json
import logging
import httpx
from urllib.parse import urlparse
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class TuyaService:
    def __init__(self):
        self.base_url = settings.tuya_base_url
        self.client_id = settings.tuya_client_id
        self.client_secret = settings.tuya_client_secret
        self.access_token = None
        self.token_expire_time = 0
        
        self.EMPTY_BODY_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        # Cache de status de dispositivos em memória (TTL: 60 segundos)
        self._devices_cache: dict[str, tuple[float, list]] = {}
        self._devices_cache_ttl = 60
        self._client: httpx.AsyncClient = None

    def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_timestamp(self) -> str:
        return str(int(time.time() * 1000))

    def _calc_sign(self, method: str, path: str, t: str, payload: str = None, access_token: str = "") -> str:
        """
        Calcula a assinatura exigida pela Tuya OpenAPI (HMAC-SHA256).
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("As credenciais da Tuya (CLIENT_ID ou CLIENT_SECRET) não estão configuradas no .env")

        # Hash do payload
        if payload is None or payload == "":
            content_hash = self.EMPTY_BODY_HASH
        else:
            content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        # StringToSign = HTTPMethod + "\n" + Content-SHA256 + "\n" + Headers + "\n" + Url
        # Headers costuma ser vazio na formatação padrão se não especificado o signature_headers
        string_to_sign = f"{method}\n{content_hash}\n\n{path}"
        
        # Message = client_id + access_token + t + string_to_sign
        message = self.client_id + access_token + t + string_to_sign
        
        # HMAC-SHA256
        sign = hmac.new(
            self.client_secret.encode("utf-8"),
            msg=message.encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest().upper()
        
        return sign

    async def get_access_token(self) -> str:
        """
        Obtém o token de acesso da Tuya e armazena em cache (na memória)
        até a expiração.
        """
        current_time = time.time()
        # Renova o token se estiver faltando menos de 60 segundos para expirar
        if self.access_token and current_time < (self.token_expire_time - 60):
            return self.access_token

        path = "/v1.0/token?grant_type=1"
        t = self._get_timestamp()
        sign = self._calc_sign("GET", path, t)

        headers = {
            "client_id": self.client_id,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256"
        }

        url = f"{self.base_url}{path}"
        logger.info(f"🔑 Solicitando novo access_token da Tuya OpenAPI...")
        
        client = self.get_client()
        response = await client.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"❌ Erro HTTP {response.status_code} ao buscar token da Tuya: {response.text}")
            raise Exception(f"Falha na API da Tuya: {response.status_code}")
            
        data = response.json()
        if not data.get("success", False):
            logger.error(f"❌ Erro da Tuya (Token): {data}")
            raise Exception(f"Erro Tuya: {data.get('msg')}")

        result = data.get("result", {})
        self.access_token = result.get("access_token")
        expire_time_seconds = result.get("expire_time", 7200)
        self.token_expire_time = current_time + expire_time_seconds
        
        logger.info("✅ Novo access_token da Tuya obtido com sucesso.")
        return self.access_token

    async def _request(self, method: str, path: str, body: dict = None) -> dict:
        """
        Gera a assinatura correta (com o access_token) e envia a requisição para a Tuya.
        """
        token = await self.get_access_token()
        t = self._get_timestamp()
        
        payload_str = ""
        if body:
            # Importante não ter espaços, conforme padrão de assinatura
            payload_str = json.dumps(body, separators=(",", ":"))
            
        sign = self._calc_sign(method.upper(), path, t, payload=payload_str, access_token=token)
        
        headers = {
            "client_id": self.client_id,
            "access_token": token,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{path}"
        
        client = self.get_client()
        if method.upper() == "GET":
            response = await client.get(url, headers=headers)
        elif method.upper() == "POST":
            response = await client.post(url, headers=headers, content=payload_str)
        elif method.upper() == "PUT":
            response = await client.put(url, headers=headers, content=payload_str)
        elif method.upper() == "DELETE":
            response = await client.delete(url, headers=headers)
        else:
            raise ValueError(f"Método HTTP {method} não suportado pelo wrapper.")
            
        data = response.json()
        if not data.get("success", False):
            logger.error(f"❌ Falha na requisição Tuya {method} {path}: {data}")
            raise Exception(f"Tuya API Error: {data.get('msg', 'Unknown Error')}")
            
        return data.get("result")

    # =========================================================================
    # ENDPOINTS ESPECÍFICOS (Baseados na Documentação)
    # =========================================================================
    
    async def get_homes_by_uid(self, uid: str) -> list:
        """
        Retorna a lista detalhada de residências (homes) vinculadas ao UID.
        GET /v1.0/users/{uid}/homes
        """
        logger.info(f"🏠 Buscando Homes para o UID {uid}...")
        path = f"/v1.0/users/{uid}/homes"
        return await self._request("GET", path)

    async def get_scenes_by_home(self, home_id: str) -> list:
        """
        Retorna as cenas configuradas dentro de uma residência específica.
        GET /v1.1/homes/{home_id}/scenes
        """
        logger.info(f"🎬 Buscando Cenas para a Home {home_id}...")
        path = f"/v1.1/homes/{home_id}/scenes"
        return await self._request("GET", path)
        
    async def execute_scene(self, home_id: str, scene_id: str) -> bool:
        """
        Executa uma cena específica em uma residência.
        POST /v1.0/homes/{home_id}/scenes/{scene_id}/trigger
        """
        logger.info(f"🚀 Executando cena {scene_id} na Home {home_id}...")
        path = f"/v1.0/homes/{home_id}/scenes/{scene_id}/trigger"
        await self._request("POST", path, body={})
        return True

    async def create_scene(self, home_id: str, name: str, background: str, actions: list) -> str:
        """
        Cria uma nova cena inteligente dentro de uma residência na Tuya OpenAPI.
        POST /v1.0/homes/{home_id}/scenes
        """
        logger.info(f"➕ Criando nova cena '{name}' na Home {home_id}...")
        path = f"/v1.0/homes/{home_id}/scenes"
        payload = {
            "name": name,
            "background": background,
            "actions": actions
        }
        res = await self._request("POST", path, body=payload)
        scene_id = res if isinstance(res, str) else res.get("scene_id")
        logger.info(f"✅ Cena '{name}' criada com sucesso! ID: {scene_id}")
        return scene_id

    async def update_scene(self, home_id: str, scene_id: str, name: str, background: str, actions: list) -> bool:
        """
        Atualiza (substituição completa) uma cena existente dentro de uma residência na Tuya OpenAPI.
        PUT /v1.0/homes/{home_id}/scenes/{scene_id}
        """
        logger.info(f"✏️ Atualizando cena {scene_id} ('{name}') na Home {home_id}...")
        path = f"/v1.0/homes/{home_id}/scenes/{scene_id}"
        payload = {
            "name": name,
            "background": background,
            "actions": actions
        }
        res = await self._request("PUT", path, body=payload)
        logger.info(f"✅ Cena {scene_id} atualizada com sucesso!")
        return res is True or res == True


    async def get_automations_by_home(self, home_id: str) -> list:
        """
        Retorna as automações/regras inteligentes de uma residência.
        GET /v1.0/homes/{home_id}/automations
        """
        logger.info(f"⚡ Buscando Automações para a Home {home_id}...")
        path = f"/v1.0/homes/{home_id}/automations"
        try:
            return await self._request("GET", path)
        except Exception as e:
            logger.error(f"⚠️ Erro em /v1.0/homes/{home_id}/automations: {e}. Tentando fallback v1.1...", extra={"status": "erro"}, exc_info=True)
            path_v11 = f"/v1.1/homes/{home_id}/automations"
            return await self._request("GET", path_v11)

    async def set_automation_status(self, home_id: str, automation_id: str, enable: bool = True) -> bool:
        """
        Ativa (enable=True) ou Desativa (enable=False) uma automação na Tuya.
        PUT /v1.0/homes/{home_id}/automations/{automation_id}/actions/enable ou /disable
        """
        action_name = "enable" if enable else "disable"
        logger.info(f"⚙️ Alterando status da automação {automation_id} para '{action_name}' na Home {home_id}...")
        path = f"/v1.0/homes/{home_id}/automations/{automation_id}/actions/{action_name}"
        try:
            await self._request("PUT", path, body={})
            return True
        except Exception as e:
            logger.error(f"⚠️ Tentando rota alternativa para automação: {e}", extra={"status": "erro"}, exc_info=True)
            path_alt = f"/v1.1/homes/{home_id}/automations/{automation_id}/actions/{action_name}"
            await self._request("PUT", path_alt, body={})
            return True

    async def get_devices_by_home(self, home_id: str) -> list:
        """
        Retorna a lista de dispositivos cadastrados em uma residência (home).
        Usa cache em memória por 60 segundos para evitar requisições desnecessárias à Tuya OpenAPI.
        GET /v1.0/homes/{home_id}/devices
        """
        now = time.time()
        if home_id in self._devices_cache:
            cache_time, cached_devices = self._devices_cache[home_id]
            if now - cache_time < self._devices_cache_ttl:
                logger.info(f"📱 Usando status de dispositivos em cache para Home {home_id} ({len(cached_devices)} dispositivos)")
                return cached_devices

        logger.info(f"📱 Consultando status de dispositivos na Tuya para Home {home_id}...")
        path = f"/v1.0/homes/{home_id}/devices"
        try:
            devices = await self._request("GET", path)
            if devices is None:
                devices = []
            self._devices_cache[home_id] = (now, devices)
            return devices
        except Exception as e:
            logger.error(f"⚠️ Erro ao buscar dispositivos da Home {home_id} na Tuya: {e}. Tentando fallback v1.1...", extra={"status": "erro"}, exc_info=True)
            try:
                path_v11 = f"/v1.1/homes/{home_id}/devices"
                devices = await self._request("GET", path_v11)
                if devices is None:
                    devices = []
                self._devices_cache[home_id] = (now, devices)
                return devices
            except Exception as e2:
                logger.error(f"⚠️ Não foi possível obter lista de dispositivos para Home {home_id}: {e2}", extra={"status": "erro"}, exc_info=True)
                return []

    async def check_home_devices_online(self, home_id: str) -> dict:
        """
        Verifica se os dispositivos IR (Emissores de Infravermelho / Hubs IR) da residência estão online.
        Como as cenas Tuya acionam os aparelhos através dos transmissores IR físicos, a verificação valida se os 
        dispositivos IR / Hubs responsáveis pelo sinal estão ativos.
        Fail-safe: Se a consulta falhar ou não houver dispositivos registrados, assume online = True.
        """
        try:
            devices = await self.get_devices_by_home(home_id)
            if not devices:
                logger.info(f"ℹ️ Nenhum dispositivo listado via API para Home {home_id}. Prosseguindo no modo fail-safe.")
                return {"all_offline": False, "online_count": 0, "total_count": 0, "checked": False}

            total_count = len(devices)
            
            # Identifica especificamente os Dispositivos IR Físicos e Hubs (categorias 'wnykq', 'wg2', 'wg', etc., ou nomes com IR/Controle/Hub/TP)
            ir_categories = {"wnykq", "wg2", "wg", "gateway", "hub"}
            ir_devices = [
                d for d in devices 
                if d.get("category") in ir_categories 
                   or "IR" in d.get("name", "").upper() 
                   or "CONTROLE" in d.get("name", "").upper() 
                   or "HUB" in d.get("name", "").upper()
                   or "TP" in d.get("name", "").upper()
            ]

            online_count = sum(1 for d in devices if d.get("online", True) is True)
            
            # Status focado nos Dispositivos IR Físicos
            ir_total = len(ir_devices)
            ir_online = sum(1 for d in ir_devices if d.get("online", True) is True)

            logger.info(
                f"📊 Status da Home {home_id}: "
                f"Total Geral: {online_count}/{total_count} online | "
                f"Dispositivos IR Físicos: {ir_online}/{ir_total} online"
            )

            # Regra de desconexão focada nos Dispositivos IR que executam as Cenas:
            # 1. Se existirem transmissores IR cadastrados e TODOS estiverem offline (ir_online == 0)
            # 2. OU se todos os dispositivos da casa estiverem offline
            all_offline = False
            if ir_total > 0 and ir_online == 0:
                logger.warning(f"🔌 Todos os transmissores IR físicos (Hubs/Controles) da Home {home_id} estão OFFLINE ({ir_online}/{ir_total}).")
                all_offline = True
            elif total_count > 0 and online_count == 0:
                all_offline = True

            return {
                "all_offline": all_offline,
                "online_count": online_count,
                "total_count": total_count,
                "ir_online": ir_online,
                "ir_total": ir_total,
                "checked": True
            }
        except Exception as e:
            logger.error(f"⚠️ Erro ao checar conectividade dos dispositivos para Home {home_id}: {e}. Ativando fallback permissivo.", extra={"status": "erro"}, exc_info=True)
            return {"all_offline": False, "online_count": 0, "total_count": 0, "checked": False}

tuya_service = TuyaService()
