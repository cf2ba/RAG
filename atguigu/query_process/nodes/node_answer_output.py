# atguigu/query_process/nodes/node_answer_output.py
import re
from typing import Any

from langchain.chat_models import init_chat_model

from atguigu.config.config import LLMConfig, MinIoConfig
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
        task_id = state.get("task_id")


        if answer:
            # 确认节点已生成话术（如“请确认目的地/景区”或“无法识别”），也必须推送 final 给前端，
            # 否则前端收不到任何答案和结束信号，只会看到“SSE 连接中断”
            put_data(task_id, "final", {"answer": answer, "image_urls": []})
            return {"answer":answer}
        else:
            chunks, item_names, prompt, rewritten_query = self.format_prompt(state)
            answer, task_id = self.generat_answer(prompt, state)
            # 将图片返回给前端：从召回文档正文中提取 Markdown 图片链接并去重
            images = self.get_image_urls(state)
            self.write_history(answer, images, item_names, rewritten_query, state, task_id)
            return {"answer":answer}

    def write_history(self, answer: str, images: list[Any], item_names: list[Any], rewritten_query: list[str],
                      state: QueryGraphState, task_id: str):
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
        # 无论有无答案都要推送 final（含答案与图片），否则前端拿不到图片 / 收不到结束信号
        put_data(task_id, "final", {"answer": answer, "image_urls": images})

    def get_image_urls(self, state: QueryGraphState) -> list[Any]:
        seen = set()  # 防止重复
        md_img_pattern = re.compile(r'!\[.*?\]\((.*?)\)')
        # 从 RRF 粗排 + rerank 精排两路结果中提取图片。
        # 重点用 rrf_chunks：图片 chunk 文本少、相关度分低，极易被 rerank 的断崖截断裁掉，
        # 而 rrf_chunks 是精排之前的 top10，图片 chunk 仍保留，才能匹配到用户问题相关的图片。
        source_chunks = (state.get("rrf_chunks") or []) + (state.get("reranked_docs") or [])
        for doc in source_chunks:
            # 检查 content 字段中的 Markdown 图片 (主要针对 Local Chunk)
            text = doc.get("content") or ""
            for img_url in md_img_pattern.findall(text):
                img_url = img_url.strip()
                if not img_url or img_url in seen:
                    continue
                # 旧数据里图片仍是相对路径 images/xxx.jpg，转成 MinIO 绝对地址，前端才能加载；
                # 新导入的数据已是 http 绝对地址，这里不会命中，直接保留
                if img_url.startswith("images/"):
                    img_url = f"http://{MinIoConfig.minio_endpoint}/{MinIoConfig.minio_bucket_name}/{MinIoConfig.minio_img_dir}/{img_url[len('images/'):]}"
                seen.add(img_url)
        return list(seen)

    def generat_answer(self, prompt: str, state: QueryGraphState) -> tuple[str, str]:
        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_base_url
        )
        messages = [
            {"role": "user", "content": prompt}
        ]
        answer = ""
        # 流式调用大模型
        res = llm.stream(input=messages)
        task_id = state.get("task_id")
        for r in res:
            put_data(task_id, "delta", {"delta": r.content})
            answer += r.content
        return answer, task_id

    def format_prompt(self, state: QueryGraphState) -> tuple[str, list, str, list[str]]:
        chunk_content = ""
        chunks = state.get("reranked_docs")
        for idx, chunk in enumerate(chunks, start=1):
            title = chunk.get("title")
            content = chunk.get("content")
            url = chunk.get("url")
            source = chunk.get("source")
            # 携带来源元数据（来源文件/文档名/地区/内容类型），供大模型生成引用来源
            file_title = chunk.get("file_title", "")
            doc_name = chunk.get("doc_name", "")
            region = chunk.get("region", "")
            content_type = chunk.get("content_type", "")
            chunk = f"[{idx}][{title}]\n来源文件:{file_title} 文档名:{doc_name} 地区:{region} 类型:{content_type}\n[{content}][{url}][{source}]\n\n"
            chunk_content += chunk
        # 要交给大模型什么内容需要自己看提示词

        history = state.get("history")
        history_content = ""
        for h in history:
            role = h.get("role")
            text = h.get("text")
            h_content = f"[{role}:{text}]\n\n"
            history_content += h_content
        item_names = state.get("item_names")
        item_names_str = ",".join(item_names)
        rewritten_query = state.get("rewritten_query")
        prompt = ANSWER_PROMPT.format(context=chunk_content, history=history_content, item_names=item_names_str,
                                      question=rewritten_query)
        prompt = prompt[:10000]
        return chunks, item_names, prompt, rewritten_query