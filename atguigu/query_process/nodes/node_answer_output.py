# atguigu/query_process/nodes/node_answer_output.py
import re

from langchain.chat_models import init_chat_model

from atguigu.config.config import LLMConfig
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.logger import logger
from atguigu.tool.mongodb import add_or_update_history
from atguigu.tool.prompt import ANSWER_PROMPT
from atguigu.tool.task_utils import put_data


class NodeAnswerOutput(NodeBase):
    """
    节点功能: 答案生成
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_answer_output"

    def process(self, state: QueryGraphState):
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """
        answer = state.get("answer")

        chunk_content =""
        if answer:
            return {"answer":answer}
        else:
            chunks = state.get("reranked_docs")
            for idx,chunk in enumerate(chunks,start=1):
                title = chunk.get("title")
                content = chunk.get("content")
                url = chunk.get("url")
                source = chunk.get("source")
                chunk = f"[{idx}][{title}]\n[{content}][{url}][{source}]\n\n"
                chunk_content+=chunk
            #要交给大模型什么内容需要自己看提示词

            history =state.get("history")
            history_content = ""
            for h in history:
                role = h.get("role")
                text = h.get("text")
                h_content = f"[{role}:{text}]\n\n"
                history_content+=h_content
            item_names = state.get("item_names")
            item_names_str = ",".join(item_names)
            rewritten_query = state.get("rewritten_query")
            prompt = ANSWER_PROMPT.format(context=chunk_content,history=history_content,item_names=item_names_str,question=rewritten_query)
            prompt = prompt[:10000]
            llm = init_chat_model(
                model=LLMConfig.item_model ,
                model_provider="openai",
                api_key=LLMConfig.openai_api_key,
                base_url=LLMConfig.openai_base_url
            )
            messages = [
                {"role":"user","content":prompt}
            ]
            answer=""
            #流式调用大模型
            res = llm.stream(input=messages)
            task_id = state.get("task_id")
            for r in res:
                put_data(task_id,"delta",{"delta":r.content})
                answer += r.content
            #将图片返回给前端
            seen = set()#防止重复
            md_img_pattern = re.compile(r'!\[.*?\]\((.*?)\)')
            for i, doc in enumerate(chunks):
                # 检查 text 字段中的 Markdown 图片 (主要针对 Local Chunk)
                text = doc.get("content")
                matches = md_img_pattern.findall(text)
                for img_url in matches:
                    img_url = img_url.strip()
                    if img_url and img_url not in seen:
                        seen.add(img_url)
                images= list(seen)
            #把这个大难变为历史记录存储到mongo
            if answer:
                session_id = state.get("session_id")
                add_or_update_history(
                    session_id,
                    role="assistant",
                    text=answer,
                    rewritten_query=rewritten_query,
                    item_names=item_names,
                    image_urls=images
                )
                put_data(task_id,"final",{"image_urls":images})
            return {"answer":answer}







        # TODO
        logger.info(f"【{self.name}】节点逻辑")

        return state