#mongo对历史记录进行增删改查
import time

from langsmith._openapi_client.types import create_online_llm_evaluator_request_param
from pymongo import MongoClient, mongo_client


from atguigu.config.config import MongoConfig
#创造链接
mongo_client = None
def get_mongo_client():
    global mongo_client
    if not mongo_client:
        mongo_client = MongoClient(MongoConfig.mongo_url)

    return mongo_client
#返回表（集合）
collection = None
db = None
def get_mongo_collection():
    mongo_client = get_mongo_client()
    global collection,db
    if  db is None:
        db = mongo_client[MongoConfig.mongo_db_name]   #等价于 use 库名
    if collection is None:
        #集合存在也不会报错
        collection = db['chat_history']   #等价于 db.createCollection("chat_history") 只是这样写如果集合存在会抛出异常
        collection.create_index([("_id",1),("ts",-1),("session_id",1)])#唯一值创索引
    return collection
#对历史记录进行增删改查的方法，查询最近的多少条历史记录
#1.获取最近的多少条历史记录，通过limit限定 ，方法目的是后期玉兔识别时要获取历史记录来识别
def get_recent_history_list(session_id,limit=10):
    collection = get_mongo_collection()
    res = collection.find({"session_id":session_id}).sort("ts",-1).limit(limit)
    print(res)#拿到的是一个游标对象，需要自己强转
    return list(res)


#增或者改历史记录  有id是修改  无id是添加
def add_or_update_history(session_id,role,text,rewritten_query=None,item_names=None,ts=None,_id=None):
    collection=get_mongo_collection()
    #全量更新和增量更新
    #为什么人在封装数据库增和改时全部合二为一写出一个方法或函数
    #应为他们在传入参数时，只有id不一样
    if _id:
        #修改操作
        data = {
            "_id":_id,
            "session_id": session_id,
            "role": role,
            "text": text,
            "rewritten_query": rewritten_query,
            "item_names": item_names,
            "ts": ts or int(time.time())
        }
        collection.update_one({"_id":_id},{"$set":data})
        return _id
        pass
    else:
        #新增操作
        data = {
            "session_id": session_id,
            "role": role,
            "text": text,
            "rewritten_query": rewritten_query,
            "item_names": item_names,
            "ts": ts or int(time.time())
        }
        result = collection.insert_one(data)
        print(result)
        return result.inserted_id
#清空历史记录
def clear_history(session_id):
    collection = get_mongo_collection()
    collection.delete_many({"session_id":session_id})
def update_item_names_and_query(ids,item_names=None,rewritten_query=None):
    collection=get_mongo_collection()
    data = {
        "rewritten_query": rewritten_query,
        "item_names": item_names
    }
    collection.update_many({"_id":{"$in":ids}},{"$set":data})

if __name__ == '__main__':
    add_or_update_history("test_001","user","咨询下烫金机")


