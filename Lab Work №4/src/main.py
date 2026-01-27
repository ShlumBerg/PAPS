from fastapi import FastAPI, Header, Request
from tinydb import TinyDB,Query
import uuid
from fastapi.responses import JSONResponse,FileResponse,Response
from pydantic import BaseModel, StrictInt, StrictStr
from typing import Optional
import time
import json
import os
app = FastAPI()
db=TinyDB('lab4db.json')
ETag_of_electronic_types_collection=db.table('ETag_of_electronic_types_collection')
Autoincrement_of_electronic_types_collection=db.table("Autoincrement_of_electronic_types_collection")
electronic_types_table=db.table('electronic_types')
electronic_types_ETags_table=db.table('electronic_types_ETags')
rules_collection=db.table("rules_collection")
rules_ETags_table=db.table("rules_ETags_table")
ETag_of_rules_collection=db.table("ETag_of_rules_collection")
post_electronic_type_idempotency_keys=db.table("post_electronic_type_idempotency_keys")
if not os.path.exists("rulesDocuments"):
    os.makedirs("rulesDocuments")
#Временная функция для инициализации БД
@app.on_event("startup")
async def startup_event():
    # Проверяем, есть ли хоть что-то в таблице с ETag коллекции ElectronicTypes
    if not ETag_of_electronic_types_collection.all():
        # Если пусто — добавляем "переменную" ETag
        ETag_of_electronic_types_collection.insert({'ETag': 1})
        print("Был добавлен ETag коллекции ElectronicTypes")
    else:
        print("ETag коллекции ElectronicTypes уже существует")
    if not ETag_of_rules_collection.all():
        ETag_of_rules_collection.insert({'ETag':1})
        print("Был добавлен ETag коллекции Rules")
    else:
        print("ETag коллекции Rules уже существует")
    if not Autoincrement_of_electronic_types_collection.all():
        Autoincrement_of_electronic_types_collection.insert({"Autoincrement":1})
        print("Был добавлен Autoincrement коллекции ElectronicTypes")
    else:
        print("Autoincrement коллекции ElectronicTypes уже существует")
#Здесь должен искаться token обращением к контейнеру Users, но пока здесь только заглушка
def checkTokenInClientsContainer(token):
    if token=="087c0099-dee9-46e2-b1c1-2af9cb306e08":
        return "Клиент"
    elif token=="90d1a522-7ebd-478f-8507-d57a3e3c3909":
        return "Инспектор"
    elif token=="41835905-b1d2-4a76-9141-3803dc1e77ba":
        return "Администратор"
    return None
def checkAuthorization(authorization:str|None):
    if authorization==None:
        return JSONResponse(status_code=401,headers={"Content-Type":"application/json","WWW-Authenticate":"Bearer"},content={"code":401,"message":"Unauthorized. Client needs Authentication through token"})
    if len(authorization.split())==0 or len(authorization.split())>0 and authorization.split()[0]!="Bearer":
        return JSONResponse(status_code=401,headers={"Content-Type":"application/json","WWW-Authenticate":"Bearer"},content={"code":401,"message":"Not supported authorization method. The only supported method is Bearer. Client needs Authentication through token"})
    token=""
    if len(authorization.split()[1])>0:
        token=authorization.split()[1]
    if checkTokenInClientsContainer(token)!=None:
        return checkTokenInClientsContainer(token)
    return JSONResponse(status_code=401,headers={"Content-Type":"application/json","WWW-Authenticate":"Bearer"},content={"code":401,"message":"Presented token does not have an active session. Please use the new token from server after you authenticate with login and password"})
#GET /v1/ElectronicTypes
class ElectronicTypes(BaseModel):
    id: StrictInt
    name: StrictStr
    ETag: StrictStr
    rule: Optional[StrictStr]=None
    price: Optional[StrictInt]=None
@app.get("/v1/ElectronicTypes")
def getElectronicTypesList(request: Request,skip:int=0,maxCount:int=10,authorization:str|None=Header(None),if_none_match:str|None=Header(None,alias="If-None-Match"),if_match:str|None=Header(None,alias="If-Match"),select:str|None=None):
    role=checkAuthorization(authorization)
    if isinstance(role, JSONResponse):     # Получили не роль, а ошибку авторизации
        return role
    if select==None:
        select=[]
    else:
        select=select.split(",")
    #Проверка на 400 Bad Request
    actual_params=set(request.query_params.keys())
    allowed_params={"skip","maxCount","select"}
    unknown_params=actual_params-allowed_params
    if len(unknown_params)>0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Unknown parameter found. Only allowed parameteres are: skip,maxCount,select"})
    if skip<0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Wrong skip parameter value. Skip value should be non-negative integer"})
    if maxCount<0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Wrong maxCount parameter value. MaxCount value should be non-negative integer"})
    allowed_select_fields={"id","name","rule","price","ETag"}
    actual_select_fields=set(select)
    unknown_select_fields=actual_select_fields-allowed_select_fields
    if len(unknown_select_fields)>0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Unknown select fields. Allowed select fields are: id,name,rule,price,ETag"})
    #Проверка на 403 Forbidden
    if role=="Клиент" and "rule" in actual_select_fields:
        return JSONResponse(status_code=403,headers={"Content-Type":"application/json"},content={"code":403,"message":"Current user does not have rights to select fields: rule"})
    #Проверка на соответствие If-Match и If-None-Match
    electronic_types_collection_current_ETag="\""+str(ETag_of_electronic_types_collection.all()[0]['ETag'])+"\""
    if if_none_match!=None and if_none_match==electronic_types_collection_current_ETag:
        return Response(status_code=304)
    if if_match!=None and if_match!=electronic_types_collection_current_ETag:
        return JSONResponse(status_code=412,headers={"Content-Type":"application/json"},content={"code":412,"message":"ETag is not equal to If-Match value"})
    #Достаём элементы из БД в соответствии с параметрами select, maxCount, skip
    if len(actual_select_fields)==0:
        actual_select_fields={"id","name","price","ETag"}
        if role!="Клиент":
            actual_select_fields.add("rule")
    if maxCount>100:
        maxCount=100
    all_electronic_types = electronic_types_table.all()
    all_electronic_types.sort(key=lambda x: x['id'])
    if skip+maxCount<=skip or skip>=len(all_electronic_types):  #Вернуть пустой список
        return JSONResponse(status_code=200,headers={"Content-Type":"application/json","ETag":electronic_types_collection_current_ETag},content={"count":0,"totalCount":len(all_electronic_types),"items":[]})
    end_ind=min(len(all_electronic_types),skip+maxCount)
    returned_electronic_types=all_electronic_types[skip:skip+maxCount]
    #Фильтр полей
    returned_items_array=[]
    for item in returned_electronic_types:
        filtered_item={k:v for k,v in item.items() if k in actual_select_fields and v!=None}
        returned_items_array.append(filtered_item)
    return JSONResponse(status_code=200,headers={"Content-Type":"application/json","ETag":electronic_types_collection_current_ETag},content={"count":len(returned_items_array),"totalCount":len(all_electronic_types),"items":returned_items_array})
#GET /v1/ElectronicTypes/{id}
@app.get("/v1/ElectronicTypes/{id}")
def getElectronicType(id:int,request: Request,authorization:str|None=Header(None),if_none_match:str|None=Header(None,alias="If-None-Match"),select:str|None=None):
    role=checkAuthorization(authorization)
    if isinstance(role, JSONResponse):     # Получили не роль, а ошибку авторизации
        return role
    if select==None:
        select=[]
    else:
        select=select.split(",")
    #Проверка на 400 Bad Request
    actual_params=set(request.query_params.keys())
    allowed_params={"select"}
    unknown_params=actual_params-allowed_params
    if len(unknown_params)>0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Unknown parameter found. Only allowed parameteres are: select"})
    allowed_select_fields={"id","name","rule","price","ETag"}
    actual_select_fields=set(select)
    unknown_select_fields=actual_select_fields-allowed_select_fields
    if len(unknown_select_fields)>0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Unknown select fields. Allowed select fields are: id,name,rule,price,ETag"})
    #Проверка на 403 Forbidden
    if role=="Клиент" and "rule" in actual_select_fields:
        return JSONResponse(status_code=403,headers={"Content-Type":"application/json"},content={"code":403,"message":"Current user does not have rights to select fields: rule"})
    #Достаём элемент из БД в соответствии с параметрами select
    if len(actual_select_fields)==0:
        actual_select_fields={"id","name","price","ETag"}
        if role!="Клиент":
            actual_select_fields.add("rule")
    query=Query()
    returned_electronic_type=electronic_types_table.get(query.id==id)
    if returned_electronic_type==None:
        return JSONResponse(status_code=404,headers={"Content-Type":"application/json"},content={"code":404,"message":"Electronic type with this id is not found"})
    #Проверка на соответствие If-None-Match
    returned_electronic_type_ETag=returned_electronic_type['ETag']
    if if_none_match!=None and if_none_match==returned_electronic_type_ETag:
        return Response(status_code=304)
    #Фильтр полей
    filtered_result={k:v for k,v in returned_electronic_type.items() if k in actual_select_fields and v!=None}
    return JSONResponse(status_code=200,headers={"Content-Type":"application/json","ETag":returned_electronic_type_ETag},content=filtered_result)
#GET /v1/Rules/{file_name}
class RulesEntry(BaseModel):
    name: StrictStr
    ETag: Optional[StrictStr] = None
    Content_Type: StrictStr = ""
@app.get("/v1/Rules/{file_name}")
def getRulesDocument(file_name:str,request:Request,authorization:str|None=Header(None),if_none_match:str|None=Header(None,alias="If-None-Match")):
    role=checkAuthorization(authorization)
    if isinstance(role, JSONResponse):     # Получили не роль, а ошибку авторизации
        return role
    #Проверка на 400 Bad Request
    actual_params=set(request.query_params.keys())
    if len(actual_params)>0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Unknown parameter found. Request should not contain any parameters, except name of the rules document!"})
    #Проверка на 404 Not Found
    query=Query()
    rules_entry=rules_collection.get(query.name==file_name)
    if rules_entry==None:
        return JSONResponse(status_code=404,headers={"Content-Type":"application/json"},content={"code":404,"message":"Rules document with presented name not found"})
    #Проверка на 403 Forbidden
    if role=="Клиент":
        return JSONResponse(status_code=403,headers={"Content-Type":"application/json"},content={"code":403,"message":"Current user does not have rights to view this resource"})
    #Проверка на соответствие If-None-Match
    if if_none_match!=None and if_none_match==rules_entry['ETag']:
        return Response(status_code=304)
    return FileResponse(headers={"ETag":rules_entry['ETag']},path=f"./rulesDocuments/{rules_entry['name']}", media_type=rules_entry['Content_Type'])
#POST /v1/ElectronicTypes
class ElectronicTypeForPost(BaseModel):
    name: StrictStr
    price: Optional[StrictInt]=None
    rule: Optional[StrictStr]=None
    
    class Config:
        extra = 'forbid'
class ElectronicTypesETag(BaseModel):
    id: StrictInt
    ETag: StrictInt
class postElectronicTypeIdempotency(BaseModel):
    key:StrictStr
    status_code: int
    response_body: dict
    response_headers: dict
    created_at: int
def cacheResponse(idempotency_key:str,responce:JSONResponse):
    new_cached_response=postElectronicTypeIdempotency(key=idempotency_key,status_code=responce.status_code,response_body=json.loads(responce.body.decode()),response_headers=dict(responce.headers),created_at=int(time.time()))
    post_electronic_type_idempotency_keys.insert(new_cached_response.dict())
    return responce
@app.post("/v1/ElectronicTypes")
def postElectronicType(body_electronic_type:ElectronicTypeForPost,request:Request,authorization:str|None=Header(None),if_match:str|None=Header(None,alias="If-Match"),content_type:str|None=Header(None,alias="Content-Type"),content_length:str|None=Header(None,alias="Content-Length"),idempotency_key:str|None=Header(None,alias="Idempotency-Key")):
    role=checkAuthorization(authorization)
    if isinstance(role, JSONResponse):     # Получили не роль, а ошибку авторизации
        return role
    #Проверка на 403 Forbidden
    if role=="Клиент" or role=="Инспектор":
        return JSONResponse(status_code=403,headers={"Content-Type":"application/json"},content={"code":403,"message":"Current user does not have rights to post resource through this method"})
    #Проверка на наличие и уникальность ключа идемпотентности
    if idempotency_key==None:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Missing required header - Idempotency-Key. Request should contain header Idempotency-Key with value of UUIDv4!"})
    try:
        idempotency_key=uuid.UUID(idempotency_key)
    except Exception:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Wrong Idempotency-Key header value format: it should be uuidv4 without any extra symbols, e.g. e09d554f-65b5-496e-8515-184a31ec8c3e!"})
    idempotency_key=str(idempotency_key)
    query_idempotency=Query()
    cached_res=post_electronic_type_idempotency_keys.get(query_idempotency.key==idempotency_key)
    if cached_res is not None:  #Уникальный ключ идемпотентности
        unix_time_created=cached_res['created_at']
        if unix_time_created+60*60*24>int(time.time()):  # Прошло меньше дня
            return JSONResponse(status_code=cached_res['status_code'],headers=cached_res['response_headers'],content=cached_res['response_body'])
        #Прошло больше дня, удаляем данный ответ из закешированных
        delete_query=Query()
        post_electronic_type_idempotency_keys.remove(delete_query.key==idempotency_key)
    #Проверка на 400 Bad Request
    actual_params=set(request.query_params.keys())
    if len(actual_params)>0:
        return cacheResponse(idempotency_key=idempotency_key,responce=JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Unknown parameter found in URL! This method does not accept any parameter!"}))
    if content_type==None:
        return cacheResponse(idempotency_key=idempotency_key,responce=JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Missing required header - Content-Type. Request should contain header Content-Type with value application/json!"}))
    if content_length==None:
        return cacheResponse(idempotency_key=idempotency_key,responce=JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Missing required header - Content-Length. Request should contain header Content-Length with content length in bytes!"}))
    try:
        content_length=int(content_length)
    except Exception:
        return cacheResponse(idempotency_key=idempotency_key,responce=JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Header Content-Length should be of type integer!"}))
    if content_type!="application/json":
        return cacheResponse(idempotency_key=idempotency_key,responce=JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Wrong Content-Type value! Only supported Content-Type value is application/json!"}))
    #Проверка на 413 Payload too large
    if content_length>100_000:
        return cacheResponse(idempotency_key=idempotency_key,responce=JSONResponse(status_code=413,headers={"Content-Type":"application/json"},content={"code":413,"message":"Payload is too large! Please send a request with payload with size of 100 000 bytes maximum!"}))
    #Проверка на 412 Precondition Failed
    electronic_types_collection_current_ETag="\""+str(ETag_of_electronic_types_collection.all()[0]['ETag'])+"\""
    if if_match!=None and electronic_types_collection_current_ETag!=if_match:
        return cacheResponse(idempotency_key=idempotency_key,responce=JSONResponse(status_code=412,headers={"Content-Type":"application/json"},content={"code":412,"message":"ETag is not equal to If-Match value!"}))
    #Проверка на 422 Unprocessable Entity
    if body_electronic_type.price!=None and body_electronic_type.price<=0:
        return cacheResponse(idempotency_key=idempotency_key,responce=JSONResponse(status_code=422,headers={"Content-Type":"application/json"},content={"code":422,"message":"Wrong price field value! Price should be of positive value!"}))
    #Проверка на наличие документа с правилами
    query=Query()
    if body_electronic_type.rule!=None and rules_collection.get(query.name==body_electronic_type.rule)==None:
        return cacheResponse(idempotency_key=idempotency_key,responce=JSONResponse(status_code=422,headers={"Content-Type":"application/json"},content={"code":422,"message":f"Cannot create resource. Not found document on server with name \"{body_electronic_type.rule}\"!"}))
    #Создание типа электроники
    cur_autoincrement_val=Autoincrement_of_electronic_types_collection.all()[0]['Autoincrement']
    #Создание вида электроники
    new_electronic_type=ElectronicTypes(name=body_electronic_type.name,id=cur_autoincrement_val,ETag="\"1\"",rule=body_electronic_type.rule,price=body_electronic_type.price)
    electronic_types_table.insert(new_electronic_type.dict())
    #Закрепление ETag нового вида электроники в коллекции для ETag
    new_ETag_collection_element=ElectronicTypesETag(id=cur_autoincrement_val,ETag=1)
    electronic_types_ETags_table.insert(new_ETag_collection_element.dict())
    #Увеличение ETag коллекции на 1
    new_value_of_ETag=ETag_of_electronic_types_collection.all()[0]['ETag']+1
    ETag_of_electronic_types_collection.update({'ETag': new_value_of_ETag})
    #Увеличение автоинкремента на 1
    new_value_of_autoincrement=cur_autoincrement_val+1
    Autoincrement_of_electronic_types_collection.update({'Autoincrement':new_value_of_autoincrement})
    #Возврат созданного вида электроники
    return cacheResponse(idempotency_key=idempotency_key,responce=JSONResponse(status_code=201,headers={"Content-Type":"application/json","ETag":"\"1\""},content=new_electronic_type.dict(exclude_none=True)))
#POST /v1/Rules/{file_name}
class RulesETagEntry(BaseModel):
    filename: str
    ETag: int
@app.post("/v1/Rules/{file_name}")
async def postRulesDocument(file_name:str,request:Request,authorization:str|None=Header(None),content_type:str|None=Header(None,alias="Content-Type"),content_length:str|None=Header(None,alias="Content-Length")):
    role=checkAuthorization(authorization)
    if isinstance(role, JSONResponse):     # Получили не роль, а ошибку авторизации
        return role
    #Проверка на 403 Forbidden
    if role=="Клиент" or role=="Инспектор":
        return JSONResponse(status_code=403,headers={"Content-Type":"application/json"},content={"code":403,"message":"Current user does not have rights to post resource through this method"})
    #Проверка на 400 Bad Request
    actual_params=set(request.query_params.keys())
    if len(actual_params)>0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Unknown parameter found in URL! This method does not accept any parameter except file to upload name!"})
    if content_type==None:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Missing required header - Content-Type. Request should contain header Content-Type!"})
    if content_length==None:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Missing required header - Content-Length. Request should contain header Content-Length with content length in bytes!"})
    try:
        content_length=int(content_length)
    except Exception:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Header Content-Length should be of type integer!"})
    #Проверка на 413 Payload too large
    if content_length>100_000_000:
        return JSONResponse(status_code=413,headers={"Content-Type":"application/json"},content={"code":413,"message":"Payload is too large! Please send a request with payload with size of 100 000 000 bytes maximum"})
    #Проверка на 409 Conflict
    query=Query()
    rules_entry=rules_collection.get(query.name==file_name)
    if rules_entry!=None:
        return JSONResponse(status_code=409,headers={"Content-Type":"application/json"},content={"code":409,"message":"Cannot post new rule. Rule with this name already exists."})
    #Чтение произвольного тела документа
    body_bytes = await request.body()
    # Проверка на соответствие реально полученного размера и заголовка
    if len(body_bytes) != content_length:
        return JSONResponse(status_code=400, content={"code": 400, "message": "Content-Length mismatch"})
    try:
        #Сохранение документа на диске
        safe_file_name = os.path.basename(file_name)
        file_path = os.path.join("./rulesDocuments", safe_file_name)
        with open(file_path, "wb") as f:
            f.write(body_bytes)
    except:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Cannot make file with such name! Probably, filename contains forbidden characters!"})
    #Добавляем или обновляем ETag для данного имени документа
    query=Query()
    ETagEntry=rules_ETags_table.get(query.filename==file_name)
    if ETagEntry==None:
        ETagEntry=RulesETagEntry(filename=file_name,ETag=1)
        rules_ETags_table.insert(ETagEntry.dict())
    else:
        ETagEntry=RulesETagEntry(filename=file_name,ETag=ETagEntry['ETag']+1)
        query2=Query()
        rules_ETags_table.update({"ETag":ETagEntry.ETag},query2.filename==file_name)
    cur_element_etag="\""+str(ETagEntry.ETag)+"\""
    #Прибавляем +1 к ETag всей коллекции
    all_collection_ETag=ETag_of_rules_collection.all()[0]['ETag']+1
    ETag_of_rules_collection.update({"ETag":all_collection_ETag})
    #Сохраняем запись о файле в БД
    new_rules_entry=RulesEntry(name=file_name,ETag=cur_element_etag,Content_Type=content_type)
    rules_collection.insert(new_rules_entry.dict())
    return JSONResponse(status_code=201, headers={"ETag":cur_element_etag,"Location": f"/v1/Rules/{file_name}"},content={"code":201,"message": "Successfully created new document with rules!"})
#GET /v1/Rules
@app.get("/v1/Rules")
def getRulesCollection(request:Request,skip:int=0,maxCount:int=10,authorization:str|None=Header(None),if_none_match:str|None=Header(None,alias="If-None-Match"),if_match:str|None=Header(None,alias="If-Match")):
    role=checkAuthorization(authorization)
    if isinstance(role, JSONResponse):     # Получили не роль, а ошибку авторизации
        return role
    #Проверка на 403 Forbidden
    if role=="Клиент":
        return JSONResponse(status_code=403,headers={"Content-Type":"application/json"},content={"code":403,"message":"Current user does not have rights to get resource through this method"})
    #Проверка на 400 Bad Request
    actual_params=set(request.query_params.keys())
    allowed_params={"skip","maxCount"}
    unknown_params=actual_params-allowed_params
    if len(unknown_params)>0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Unknown parameter found. Only allowed parameteres are: skip,maxCount"})
    if skip<0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Wrong skip parameter value. Skip value should be non-negative integer"})
    if maxCount<0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Wrong maxCount parameter value. MaxCount value should be non-negative integer"})
    #Проверка на соответствие If-Match и If-None-Match
    current_rules_collection_ETag="\""+str(ETag_of_rules_collection.all()[0]['ETag'])+"\""
    if if_none_match!=None and if_none_match==current_rules_collection_ETag:
        return Response(status_code=304)
    if if_match!=None and if_match!=current_rules_collection_ETag:
        return JSONResponse(status_code=412,headers={"Content-Type":"application/json"},content={"code":412,"message":"ETag is not equal to If-Match value"})
    #Получение элементов коллекции с учётом пагинации
    if maxCount>100:
        maxCount=100
    all_rules_entries = rules_collection.all()
    if skip+maxCount<=skip or skip>=len(all_rules_entries):  #Вернуть пустой список
        return JSONResponse(status_code=200,headers={"Content-Type":"application/json","ETag":current_rules_collection_ETag},content={"count":0,"totalCount":len(all_rules_entries),"items":[]})
    end_ind=min(len(all_rules_entries),skip+maxCount)
    returned_rules=all_rules_entries[skip:skip+maxCount]
    #Фильтр полей
    returned_items_array=[]
    for item in returned_rules:
        filtered_item={k:v for k,v in item.items() if k in set(["name","ETag"])}
        returned_items_array.append(filtered_item)
    return JSONResponse(status_code=200,headers={"Content-Type":"application/json","ETag":current_rules_collection_ETag},content={"count":len(returned_items_array),"totalCount":len(all_rules_entries),"items":returned_items_array})
#DELETE /v1/Rules/{file_name}
@app.delete("/v1/Rules/{file_name}")
def deleteRule(request:Request,file_name:str,authorization:str|None=Header(None),if_none_match:str|None=Header(None,alias="If-None-Match"),if_match:str|None=Header(None,alias="If-Match")):
    role=checkAuthorization(authorization)
    if isinstance(role, JSONResponse):     # Получили не роль, а ошибку авторизации
        return role
    #Проверка на 403 Forbidden
    if role=="Клиент" or role=="Инспектор":
        return JSONResponse(status_code=403,headers={"Content-Type":"application/json"},content={"code":403,"message":"Current user does not have rights to delete resource through this method"})
    #Проверка на 400 Bad Request
    actual_params=set(request.query_params.keys())
    if len(actual_params)>0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Unknown parameter found in URL! Only allowed parameter is: file_name"})
    #Проверка на 404 Not Found
    query=Query()
    rule_entry=rules_collection.get(query.name==file_name)
    if rule_entry==None:
        return JSONResponse(status_code=404,headers={"Content-Type":"application/json"},content={"code":404,"message":"Cannot delete document. Document with rules with this name not found!"})
    #Проверка на соответствие If-Match и If-None-Match
    current_ETag=str(rule_entry['ETag'])
    print("if-match header:",if_match)
    print("curremt_ETag:",current_ETag)
    if if_none_match!=None and if_none_match==current_ETag:
        return Response(status_code=304)
    if if_match!=None and if_match!=current_ETag:
        return JSONResponse(status_code=412,headers={"Content-Type":"application/json"},content={"code":412,"message":"ETag is not equal to If-Match value"})
    #Удаляем файл
    safe_file_name = os.path.basename(file_name)
    file_path = os.path.join("./rulesDocuments", safe_file_name)
    os.remove(file_path)
    #Обновляем ETag элемента
    query=Query()
    cur_ETag_int=rules_ETags_table.get(Query().filename==file_name)['ETag']
    rules_ETags_table.update({"ETag":cur_ETag_int+1},query.filename==file_name)
    #Удаляем запись о элементе
    query=Query()
    rules_collection.remove(query.name==file_name)
    #Прибавляем +1 к ETag всей коллекции
    all_collection_ETag=ETag_of_rules_collection.all()[0]['ETag']+1
    ETag_of_rules_collection.update({"ETag":all_collection_ETag})
    #Возвращаем ответ
    return Response(status_code=204)
#PUT /v1/Rules/{file_name}
@app.put("/v1/Rules/{file_name}")
async def putRule(request:Request,file_name:str,authorization:str|None=Header(None),content_length:str|None=Header(None,alias="Content-Length"),content_type:str|None=Header(None,alias="Content-Type")):
    role=checkAuthorization(authorization)
    if isinstance(role, JSONResponse):     # Получили не роль, а ошибку авторизации
        return role
    #Проверка на 403 Forbidden
    if role=="Клиент" or role=="Инспектор":
        return JSONResponse(status_code=403,headers={"Content-Type":"application/json"},content={"code":403,"message":"Current user does not have rights to put resource through this method"})
    #Проверка на 400 Bad Request
    actual_params=set(request.query_params.keys())
    if len(actual_params)>0:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Unknown parameter found in URL! This method does not accept any parameter except file to upload name!"})
    if content_type==None:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Missing required header - Content-Type. Request should contain header Content-Type!"})
    if content_length==None:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Missing required header - Content-Length. Request should contain header Content-Length with content length in bytes!"})
    try:
        content_length=int(content_length)
    except Exception:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Header Content-Length should be of type integer!"})
    #Проверка на 413 Payload too large
    if content_length>100_000_000:
        return JSONResponse(status_code=413,headers={"Content-Type":"application/json"},content={"code":413,"message":"Payload is too large! Please send a request with payload with size of 100 000 000 bytes maximum"})
    #Чтение произвольного тела документа
    body_bytes = await request.body()
    # Проверка на соответствие реально полученного размера и заголовка
    if len(body_bytes) != content_length:
        return JSONResponse(status_code=400, content={"code": 400, "message": "Content-Length mismatch"})
    try:
        #Сохранение документа на диске
        safe_file_name = os.path.basename(file_name)
        file_path = os.path.join("./rulesDocuments", safe_file_name)
        with open(file_path, "wb") as f:
            f.write(body_bytes)
    except:
        return JSONResponse(status_code=400,headers={"Content-Type":"application/json"},content={"code":400,"message":"Cannot make file with such name! Probably, filename contains forbidden characters!"})
    #Добавляем или обновляем ETag для данного имени документа
    query=Query()
    ETagEntry=rules_ETags_table.get(query.filename==file_name)
    if ETagEntry==None:
        ETagEntry=RulesETagEntry(filename=file_name,ETag=1)
        rules_ETags_table.insert(ETagEntry.dict())
    else:
        ETagEntry=RulesETagEntry(filename=file_name,ETag=ETagEntry['ETag']+1)
        query2=Query()
        rules_ETags_table.update({"ETag":ETagEntry.ETag},query2.filename==file_name)
    cur_element_etag="\""+str(ETagEntry.ETag)+"\""
    #Прибавляем +1 к ETag всей коллекции
    all_collection_ETag=ETag_of_rules_collection.all()[0]['ETag']+1
    ETag_of_rules_collection.update({"ETag":all_collection_ETag})
    query=Query()
    existing_entry=rules_collection.get(query.name==file_name)
    if existing_entry==None:
        new_rules_entry=RulesEntry(name=file_name,ETag=cur_element_etag,Content_Type=content_type)
        rules_collection.insert(new_rules_entry.dict())
        return JSONResponse(status_code=201, headers={"ETag":cur_element_etag,"Location": f"/v1/Rules/{file_name}"},content={"code":201,"message": "Successfully created new document with rules!"})
    query=Query()
    rules_collection.update({"Content_Type":content_type,"ETag":cur_element_etag},query.name==file_name)
    return Response(status_code=204,headers={"ETag":cur_element_etag,"Location":f"/v1/Rules/{file_name}"})
