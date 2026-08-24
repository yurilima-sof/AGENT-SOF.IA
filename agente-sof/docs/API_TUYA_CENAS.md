# Documentação da API de Cenas Inteligentes (Tuya OpenAPI)

Esta documentação descreve as rotas, estruturas de payload, comportamentos e exemplos de código para **Criação**, **Atualização** e **Execução** de Cenas Inteligentes na plataforma **Tuya OpenAPI**, utilizadas pelo projeto `agente-sof`.

---

## 📌 Visão Geral

A Tuya OpenAPI disponibiliza endpoints RESTful para gerenciar as cenas inteligentes (*Smart Scenes*) vinculadas às residências (*Homes*). 

- **Endereço Base**: `https://openapi.tuyaus.com` (Região US/Americas)
- **Autenticação**: Assinatura `HMAC-SHA256` nos cabeçalhos HTTP com `client_id`, `access_token`, `t` (timestamp) e `sign`.

---

## 1. Criar Cena (*Create Scene*)

Cria uma nova cena inteligente associada a uma residência específica.

### 🌐 Endpoint HTTP
```http
POST /v1.0/homes/{home_id}/scenes
```

### 📍 Parâmetros da URI
| Parâmetro | Tipo | Obrigatório | Descrição |
| :--- | :--- | :--- | :--- |
| `home_id` | `string` | **Sim** | ID numérico da residência na Tuya (ex: `265054363`). |

### 📦 Esquema do Body (JSON)

> [!IMPORTANT]
> O corpo da requisição deve conter todos os campos obrigatórios `name`, `background` e `actions`.

| Campo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :--- | :--- |
| `name` | `string` | **Sim** | Nome identificador da cena (ex: `"PE - Sala SOF 22C Fan Medio"`). |
| `background` | `string` | **Sim** | URL da imagem de capa/fundo da cena no aplicativo. |
| `actions` | `array[object]` | **Sim** | Lista encadeada de ações a serem executadas sequencialmente. |

#### Estrutura dos Objetos em `actions`:

##### Ação do Tipo `delay` (Atraso):
```json
{
  "action_executor": "delay",
  "executor_property": {
    "hours": "0",
    "minutes": "0",
    "seconds": "5"
  }
}
```

##### Ação do Tipo `dpIssue` (Comando para Dispositivo / DP):
```json
{
  "action_executor": "dpIssue",
  "entity_id": "eb18e4bcfcf423fd83ohtm",
  "executor_property": {
    "T": "22",
    "F": "2",
    "PowerOn": "PowerOn"
  }
}
```
*Legenda de propriedades para Ar Condicionado IR (`infrared_ac`):*
- `PowerOn`: `"PowerOn"` (Ligar) / `PowerOff`: `"PowerOff"` (Desligar)
- `T`: Temperatura desejada em °C (ex: `"22"`, `"20"`)
- `F`: Velocidade da ventoinha (ex: `"0"` Auto, `"1"` Baixo, `"2"` Médio, `"3"` Alto)

---

### 💻 Exemplo de Requisição (cURL)

```bash
curl -X POST "https://openapi.tuyaus.com/v1.0/homes/265054363/scenes" \
  -H "client_id: 48dg45cqx8ccvy4rsagq" \
  -H "access_token: fcbdc0806e5f6d7f0eb9ffbf3914713f" \
  -H "sign_method: HMAC-SHA256" \
  -H "t: 1787251983000" \
  -H "sign: 8F...9A" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "PE - Sala SOF 22C Fan Medio",
    "background": "https://images.tuyacn.com/smart/rule/cover/sport.png",
    "actions": [
      {
        "action_executor": "delay",
        "executor_property": { "hours": "0", "minutes": "0", "seconds": "5" }
      },
      {
        "action_executor": "dpIssue",
        "entity_id": "eb18e4bcfcf423fd83ohtm",
        "executor_property": { "T": "22", "F": "2", "PowerOn": "PowerOn" }
      }
    ]
  }'
```

### 📤 Exemplo de Resposta de Sucesso (HTTP 200)

```json
{
  "result": "xmDTaUsJuubH7i9N",
  "success": true,
  "t": 1787251983000,
  "tid": "495915b69cc811f1973c22f2dd4e48eb"
}
```
*O campo `result` retorna uma string contendo o `scene_id` gerado.*

---

## 2. Atualizar Cena (*Update Scene*)

Realiza a **substituição completa (*Full Replace*)** de uma cena pré-existente.

> [!WARNING]
> O endpoint usa o método HTTP `PUT`. **Todos os campos (`name`, `background`, `actions`) são obrigatórios**. Este endpoint substitui completamente o registro na Tuya (não é um *PATCH* parcial).

### 🌐 Endpoint HTTP
```http
PUT /v1.0/homes/{home_id}/scenes/{scene_id}
```

### 📍 Parâmetros da URI
| Parâmetro | Tipo | Obrigatório | Descrição |
| :--- | :--- | :--- | :--- |
| `home_id` | `string` | **Sim** | ID numérico da residência na Tuya. |
| `scene_id` | `string` | **Sim** | ID único da cena a ser substituída (ex: `"xmDTaUsJuubH7i9N"`). |

### 📦 Esquema do Body (JSON)
Estrutura idêntica à de criação (`POST`).

---

### 💻 Exemplo de Requisição (cURL)

```bash
curl -X PUT "https://openapi.tuyaus.com/v1.0/homes/265054363/scenes/xmDTaUsJuubH7i9N" \
  -H "client_id: 48dg45cqx8ccvy4rsagq" \
  -H "access_token: fcbdc0806e5f6d7f0eb9ffbf3914713f" \
  -H "sign_method: HMAC-SHA256" \
  -H "t: 1787252178000" \
  -H "sign: 3C...7E" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "teste20/08",
    "background": "https://images.tuyacn.com/smart/rule/cover/sport.png",
    "actions": [
      {
        "action_executor": "delay",
        "executor_property": { "hours": "0", "minutes": "0", "seconds": "5" }
      },
      {
        "action_executor": "dpIssue",
        "entity_id": "eb18e4bcfcf423fd83ohtm",
        "executor_property": { "T": "20", "F": "2", "PowerOn": "PowerOn" }
      }
    ]
  }'
```

### 📤 Exemplo de Resposta de Sucesso (HTTP 200)

```json
{
  "result": true,
  "success": true,
  "t": 1787252178000,
  "tid": "5c52c6129cc811f1a1f25a9d3d3f4bc4"
}
```
*Em caso de sucesso, o campo `result` retorna `true`.*

---

## 3. Disparar / Executar Cena (*Trigger Scene*)

Executa uma cena cadastrada manualmente sob demanda.

### 🌐 Endpoint HTTP
```http
POST /v1.0/homes/{home_id}/scenes/{scene_id}/trigger
```

### 📤 Exemplo de Resposta de Sucesso (HTTP 200)

```json
{
  "result": true,
  "success": true,
  "t": 1787252200000,
  "tid": "7a91b2c3d4e5f6a1b2c3d4e5f6a1b2c3"
}
```

---

## 🐍 Uso no Código Python (`TuyaService`)

O módulo `app.services.tuya_service.TuyaService` disponibiliza os métodos prontos assíncronos:

```python
from app.services.tuya_service import tuya_service

async def exemplo_uso():
    home_id = "265054363"
    entity_id = "eb18e4bcfcf423fd83ohtm"

    actions_criar = [
        {
            "action_executor": "delay",
            "executor_property": {"hours": "0", "minutes": "0", "seconds": "5"}
        },
        {
            "action_executor": "dpIssue",
            "entity_id": entity_id,
            "executor_property": {"T": "22", "F": "2", "PowerOn": "PowerOn"}
        }
    ]

    # 1. Criar Cena
    scene_id = await tuya_service.create_scene(
        home_id=home_id,
        name="PE - Sala SOF 22C",
        background="https://images.tuyacn.com/smart/rule/cover/sport.png",
        actions=actions_criar
    )
    print(f"Cena criada com ID: {scene_id}")

    # 2. Atualizar Cena (Full Replace)
    actions_atualizar = [
        {
            "action_executor": "delay",
            "executor_property": {"hours": "0", "minutes": "0", "seconds": "5"}
        },
        {
            "action_executor": "dpIssue",
            "entity_id": entity_id,
            "executor_property": {"T": "20", "F": "2", "PowerOn": "PowerOn"}
        }
    ]

    sucesso_update = await tuya_service.update_scene(
        home_id=home_id,
        scene_id=scene_id,
        name="teste20/08",
        background="https://images.tuyacn.com/smart/rule/cover/sport.png",
        actions=actions_atualizar
    )
    print(f"Cena atualizada: {sucesso_update}")

    # 3. Executar Cena
    sucesso_trigger = await tuya_service.execute_scene(home_id, scene_id)
    print(f"Cena disparada: {sucesso_trigger}")
```

---

## ❌ Tabela de Tratameno de Erros Tuya

| Código Tuya (`code`) | Mensagem de Erro | Causa Provável | Solução |
| :--- | :--- | :--- | :--- |
| `1108` | `uri path invalid` | Rota incorreta (ex: tentar usar `/v1.1` em vez de `/v1.0`). | Usar a rota oficial `/v1.0/homes/{home_id}/scenes`. |
| `1109` | `param is illegal` | Campo obrigatório ausente ou propriedade inválida. | Verificar se `name`, `background` e `actions` estão presentes no body. |
| `1010` | `token invalid` | Access token expirado ou inválido. | O `tuya_service` renova o token automaticamente via `get_access_token()`. |
