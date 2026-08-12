# atguigu/query_process/nodes/node_rrf.py

from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NodeRrf(NodeBase):
    """
    节点功能：Reciprocal Rank Fusion 倒数排名融合算法
    将多路召回的结果（原始向量检索、HyDE向量检索、后续可扩展Web检索）进行加权融合重排序。
    算法原理：利用文档在不同召回通路中的排名计算融合得分，相同文档多条通路命中则分数累加，
    缓解单一检索策略带来的排序偏差，提升召回结果相关性。
    """

    # 覆盖基类的 name 属性，用于工作流图中标识当前节点名称
    name: str = "node_rrf"

    def process(self, state: QueryGraphState):
        """
        RRF融合主处理逻辑
        :param state: 工作流全局状态对象，承载上下游节点数据
        :return: dict 更新后的状态字段，输出融合重排后的文档切片列表 rrf_chunks
        """

        # 从状态中获取两路向量召回结果
        embeddings_chunks = state.get("embeddings_chunks")
        hyde_embeddings_chunks = state.get("hyde_embeddings_chunks")

        # 合法性校验：原始向量召回结果不能为空
        if not embeddings_chunks:
            logger.error("向量检索结果未上传")
            raise Exception("向量检索结果未上传")
        # 合法性校验：HyDE假设检索结果不能为空
        if not hyde_embeddings_chunks:
            logger.error("假设检索结果未上传")
            raise Exception("假设检索结果未上传")

        # 配置多路召回通路：(召回文档列表, 通路权重)
        # 后续新增Web召回等通路直接在此追加元组即可扩展
        weight_embedding = [
            (embeddings_chunks, 1),
            (hyde_embeddings_chunks, 1)
        ]

        # 字典用于存储全部文档，key=文档唯一id，value=文档完整对象，实现文档去重 + 分数累加
        final_chunks_dict = {}

        # 遍历每一路召回结果，逐文档计算RRF融合得分
        for chunks, weight in weight_embedding:
            # idx从1开始：检索排名从第1名算起，符合RRF算法定义
            for idx, chunk in enumerate(chunks, start=1):
                chunk_id = chunk.get("id")
                # RRF核心计算公式：原始相似度分数 + weight / (rank + k)
                # k=60 为平滑常数，行业通用取值，降低排名靠后文档的权重影响
                chunk_score = chunk.get("score") + weight / (idx + 60)

                # 判断文档是否在其它通路已经出现
                if chunk_id in final_chunks_dict:
                    # 重复文档：累加多路计算得到的RRF分数
                    final_chunks_dict.get(chunk_id)["score"] += chunk_score
                else:
                    # 首次出现：覆盖原文档score为当前通路计算后的RRF得分，存入字典
                    chunk["score"] = chunk_score
                    final_chunks_dict[chunk_id] = chunk

        # 打印融合完成后的全部文档字典（调试日志）
        # print(json_format_tool(final_chunks_dict))

        # 根据融合后总分数降序排序
        rrf_chunks = sorted(final_chunks_dict.values(), key=lambda x: x["score"], reverse=True)

        # 返回前10条作为RRF重排结果写入状态
        return {
            "rrf_chunks": rrf_chunks[:10]
        }


if __name__ == '__main__':
    # 单元测试入口，本地调试执行
    node = NodeRrf()
    # 模拟工作流state数据，两路召回测试数据
    mock_state = {
        "embeddings_chunks": [
            {
                "item_name": "BrotherHAK180烫金机",
                "content": "## HAK 180 烫金机\n\n产品安全手册（简体中文）\n\n感谢您购买 HAK 180 烫金机。\n\n在使用本设备之前，请先阅读本手册，包括所有预防措施。阅读本手册后，请妥善保管。\n\n有关使用本设备的更多信息，请参阅使用说明书，其可在兄弟 (中国)商业有限公司技术服务支持网站 http://www.95105369.com/Web/Manuals.aspx 上找到。建议您先通读使用说明书，再使用本设备。\n\n如需获得常见问题解答、故障排除和说明书，请访问\n\nhttp://www.95105369.com。\n\n对于本设备所有者不遵守本指南中规定的说明操作而导致的损害，Brother 不承担任何责任。",
                "id": 468219061222798546,
                "file_title": "hak180产品安全手册",
                "title": "## HAK 180 烫金机",
                "score": 0.8347935676574707,
                "source": "local"
            },
            {
                "item_name": "BrotherHAK180烫金机",
                "content": "## HAK 180 烫金机\n\n•\t对于保养、调整或维修事宜，请联系 Brother 呼叫中心或您当地的Brother 经销商。\n\n•\t如果本设备工作不正常或发生任何错误，请关闭本设备，拔下所有电缆，然后联系 Brother 呼叫中心或您当地的 Brother 经销商。\n\n•\t本文档中提供的信息可能会随时更改，恕不另行通知。\n\n•\t严禁未经授权擅自复制或重制本文档的任何部分或全部内容。\n\n•\t请注意，对于使用通过本设备制作的产品造成的任何损坏或利润损失，或者故障、维修导致的数据消失或更改，或者第三方提出的任何索赔，我们不承担任何责任。",
                "id": 468219061222798547,
                "file_title": "hak180产品安全手册",
                "title": "## HAK 180 烫金机",
                "score": 0.8282701969146729,
                "source": "local"
            },
            {
                "item_name": "BrotherHAK180烫金机",
                "content": "## 设备\n\n•\t请勿拆解本设备。拆解本设备可能会导致火灾或触电。\n\n•\t请勿尝试自行维修本设备。打开或拆下盖子可能使您接触到危险电压点以及带来其他风险，并且可能使您的保修失效。对于所有维修事宜，请联系 Brother 呼叫中心或您当地的 Brother 经销商。\n\n•\t请在以下环境使用本设备：温度保持在 10 °C 和 32 °C 之间，湿度保持在 20% 和 80% 之间，无冷凝。\n\n•\t请勿使本设备受到阳光直射、过热、接触明火、腐蚀性气体、湿气或灰尘。否则可能产生触电、短路或火灾的风险，从而导致损坏设备和/或导致设备无法运行。\n\n•\t请勿将设备放在加热器、空调、电风扇或水附近。",
                "id": 468219061222798550,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "score": 0.8214895129203796,
                "source": "local"
            },
            {
                "item_name": "BrotherHAK180烫金机",
                "content": "## 设备\n\n•\t请先阅读这本手册，再尝试操作本设备或尝试进行任何维护。不按照这些说明操作可能会提高发生人员受伤或财产损坏（包括火灾、触电、烧伤或窒息所致）的风险。对于本设备所有者不遵守本指南中规定的说明操作而导致的损害，Brother 不承担任何责任。\n\n•\t请勿在未去除所有包装材料的情况下使用本设备，包括本设备内部的任何附加的包装材料。否则可能会产生火灾的风险。\n\n•\t请勿拆解本设备。拆解本设备可能会导致火灾或触电。",
                "id": 468219061222798549,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "score": 0.8149500489234924,
                "source": "local"
            },
            {
                "item_name": "BrotherHAK180烫金机",
                "content": "![](images/677a08ee041965bbbdb6b483d6c17d5aaa36a26b6dc96870a2019f0307b8616f.jpg)  \nD01WD7001-00\n\nSCHN\n",
                "id": 468219061222798545,
                "file_title": "hak180产品安全手册",
                "title": "无标题",
                "score": 0.8105827569961548,
                "source": "local"
            },
            {
                "item_name": "BrotherHAK180烫金机",
                "content": "## 设备\n\n如果遵守了操作说明进行操作，但是设备不能正确运行，请仅调整操作说明中涵盖的控制。错误调整其他控制可能导致损坏并且通常需要合格技术进行全面工作以将本设备恢复到正常操作。Brother不建议使用 Brother 正品烫金膜盒以外的其他品牌烫金膜盒。如果使用与本设备不兼容的耗材导致损坏本设备的任何零件，由此导致的任何维修可能不在保修范围内。\n",
                "id": 468219061222798562,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "score": 0.8090631365776062,
                "source": "local"
            },
            {
                "item_name": "BrotherHAK180烫金机",
                "content": "## 设备\n\n![](images/f3349cded08d6686a93d0a81b9a64ec1e50d9a82cbb88541b37027f085813a15.jpg)  \n儎⑟ഴḽ䆜઀ᛞ࠽व䀜᪮儎⑟Ⲻ䇴༽䜞ԬȾ\n\n![](images/501bb8d2d681e4502d87badb15a68939eadfa086d309c3599f1c36b0bc559177.jpg)",
                "id": 468219061222798554,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "score": 0.8083792328834534,
                "source": "local"
            },
            {
                "item_name": "BrotherHAK180烫金机",
                "content": "## 设备\n\n•\t请勿在卡纸或有纸张散落在设备内部的情况下尝试使用本设备。纸张与定影单元长时间接触可能导致火灾。\n\n请勿使用任何易燃物品、任何类型的喷雾剂包含酒精或氨水的有机溶剂/液体来清洁本设备的内部或外部。否则可能导致火灾。请改用无绒干抹布。有关如何清洁本设备的说明，请参阅 。\n\n•\t请勿将本设备放在化学品附近，或者将本设备放置在可能会泼溅到化学品的位置。万一化学品接触本设备，则存在火灾或触电的风险。特别是有机溶剂或液体（如苯、油漆稀释剂、抛光剂或除臭剂）可能导致塑料盖和/或电缆溶解或分解，从而产生火灾或触电的风险。这些化学品或其他化学品可能导致本设备故障或褪色。",
                "id": 468219061222798552,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "score": 0.8042272329330444,
                "source": "local"
            },
            {
                "item_name": "BrotherHAK180烫金机",
                "content": "## 设备\n\n•\t将本设备放置在平整、水平且稳定的表面上（如桌面），避免震动和冲击。\n\n•\t将本设备放置在通风良好的环境中。\n\n•\t为了防止人员受伤，请谨慎操作，避免将手指放置在图中所示的区域中。\n\n![](images/c61a7f4e923881679f747508ae309c39dc221685344b068009256b1b3a40cc00.jpg)\n\n![](images/5067b2891ca4f761e2874921e0eb433aa742afbf38ca8dc509afecbf0aa6a6b5.jpg)\n",
                "id": 468219061222798558,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "score": 0.7109385132789612,
                "source": "local"
            },
            {
                "item_name": "BrotherHAK180烫金机",
                "content": "## 为设备选择一个安全的位置\n\n•\t提起本设备时，请使用双手抓稳本设备的两侧。如果抓住的是进纸托板和出纸盒，它们可能会掉下来。必须通过将双手放在本设备下面来搬运本设备。\n\n![](images/cc5ee1ac24ebb2707d40dc7a234a8b243f55f5bf08fabc683859be6fdf096ffa.jpg)  \n确保本设备的任何部位均未伸出设备所在的桌面或支架。特别是当本设备位于桌面、支架等边缘时，请勿让出纸盒打开。确保本设备位于平整、水平且稳定的表面上，避免震动。不遵守这些预防措施可能导致设备跌落，从而导致用户的人身伤害以及设备严重损坏。",
                "id": 468219061222798560,
                "file_title": "hak180产品安全手册",
                "title": "## 为设备选择一个安全的位置",
                "score": 0.6864750385284424,
                "source": "local"
            }
        ],
        "hyde_embeddings_chunks": [
            {
                "id": 468219061222798546,
                "file_title": "hak180产品安全手册",
                "title": "## HAK 180 烫金机",
                "content": "## HAK 180 烫金机\n\n产品安全手册（简体中文）\n\n感谢您购买 HAK 180 烫金机。\n\n在使用本设备之前，请先阅读本手册，包括所有预防措施。阅读本手册后，请妥善保管。\n\n有关使用本设备的更多信息，请参阅使用说明书，其可在兄弟 (中国)商业有限公司技术服务支持网站 http://www.95105369.com/Web/Manuals.aspx 上找到。建议您先通读使用说明书，再使用本设备。\n\n如需获得常见问题解答、故障排除和说明书，请访问\n\nhttp://www.95105369.com。\n\n对于本设备所有者不遵守本指南中规定的说明操作而导致的损害，Brother 不承担任何责任。",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.8562303185462952,
                "source": "local"
            },
            {
                "id": 468219061222798547,
                "file_title": "hak180产品安全手册",
                "title": "## HAK 180 烫金机",
                "content": "## HAK 180 烫金机\n\n•\t对于保养、调整或维修事宜，请联系 Brother 呼叫中心或您当地的Brother 经销商。\n\n•\t如果本设备工作不正常或发生任何错误，请关闭本设备，拔下所有电缆，然后联系 Brother 呼叫中心或您当地的 Brother 经销商。\n\n•\t本文档中提供的信息可能会随时更改，恕不另行通知。\n\n•\t严禁未经授权擅自复制或重制本文档的任何部分或全部内容。\n\n•\t请注意，对于使用通过本设备制作的产品造成的任何损坏或利润损失，或者故障、维修导致的数据消失或更改，或者第三方提出的任何索赔，我们不承担任何责任。",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.839849591255188,
                "source": "local"
            },
            {
                "id": 468219061222798549,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "content": "## 设备\n\n•\t请先阅读这本手册，再尝试操作本设备或尝试进行任何维护。不按照这些说明操作可能会提高发生人员受伤或财产损坏（包括火灾、触电、烧伤或窒息所致）的风险。对于本设备所有者不遵守本指南中规定的说明操作而导致的损害，Brother 不承担任何责任。\n\n•\t请勿在未去除所有包装材料的情况下使用本设备，包括本设备内部的任何附加的包装材料。否则可能会产生火灾的风险。\n\n•\t请勿拆解本设备。拆解本设备可能会导致火灾或触电。",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.8329867124557495,
                "source": "local"
            },
            {
                "id": 468219061222798562,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "content": "## 设备\n\n如果遵守了操作说明进行操作，但是设备不能正确运行，请仅调整操作说明中涵盖的控制。错误调整其他控制可能导致损坏并且通常需要合格技术进行全面工作以将本设备恢复到正常操作。Brother不建议使用 Brother 正品烫金膜盒以外的其他品牌烫金膜盒。如果使用与本设备不兼容的耗材导致损坏本设备的任何零件，由此导致的任何维修可能不在保修范围内。\n",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.8310372233390808,
                "source": "local"
            },
            {
                "id": 468219061222798550,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "content": "## 设备\n\n•\t请勿拆解本设备。拆解本设备可能会导致火灾或触电。\n\n•\t请勿尝试自行维修本设备。打开或拆下盖子可能使您接触到危险电压点以及带来其他风险，并且可能使您的保修失效。对于所有维修事宜，请联系 Brother 呼叫中心或您当地的 Brother 经销商。\n\n•\t请在以下环境使用本设备：温度保持在 10 °C 和 32 °C 之间，湿度保持在 20% 和 80% 之间，无冷凝。\n\n•\t请勿使本设备受到阳光直射、过热、接触明火、腐蚀性气体、湿气或灰尘。否则可能产生触电、短路或火灾的风险，从而导致损坏设备和/或导致设备无法运行。\n\n•\t请勿将设备放在加热器、空调、电风扇或水附近。",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.8300616145133972,
                "source": "local"
            },
            {
                "id": 468219061222798558,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "content": "## 设备\n\n•\t将本设备放置在平整、水平且稳定的表面上（如桌面），避免震动和冲击。\n\n•\t将本设备放置在通风良好的环境中。\n\n•\t为了防止人员受伤，请谨慎操作，避免将手指放置在图中所示的区域中。\n\n![](images/c61a7f4e923881679f747508ae309c39dc221685344b068009256b1b3a40cc00.jpg)\n\n![](images/5067b2891ca4f761e2874921e0eb433aa742afbf38ca8dc509afecbf0aa6a6b5.jpg)\n",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.7194610834121704,
                "source": "local"
            },
            {
                "id": 468219061222798554,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "content": "## 设备\n\n![](images/f3349cded08d6686a93d0a81b9a64ec1e50d9a82cbb88541b37027f085813a15.jpg)  \n儎⑟ഴḽ䆜઀ᛞ࠽व䀜᪮儎⑟Ⲻ䇴༽䜞ԬȾ\n\n![](images/501bb8d2d681e4502d87badb15a68939eadfa086d309c3599f1c36b0bc559177.jpg)",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.7049278616905212,
                "source": "local"
            },
            {
                "id": 468219061222798545,
                "file_title": "hak180产品安全手册",
                "title": "无标题",
                "content": "![](images/677a08ee041965bbbdb6b483d6c17d5aaa36a26b6dc96870a2019f0307b8616f.jpg)  \nD01WD7001-00\n\nSCHN\n",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.7047582864761353,
                "source": "local"
            },
            {
                "id": 468219061222798560,
                "file_title": "hak180产品安全手册",
                "title": "## 为设备选择一个安全的位置",
                "content": "## 为设备选择一个安全的位置\n\n•\t提起本设备时，请使用双手抓稳本设备的两侧。如果抓住的是进纸托板和出纸盒，它们可能会掉下来。必须通过将双手放在本设备下面来搬运本设备。\n\n![](images/cc5ee1ac24ebb2707d40dc7a234a8b243f55f5bf08fabc683859be6fdf096ffa.jpg)  \n确保本设备的任何部位均未伸出设备所在的桌面或支架。特别是当本设备位于桌面、支架等边缘时，请勿让出纸盒打开。确保本设备位于平整、水平且稳定的表面上，避免震动。不遵守这些预防措施可能导致设备跌落，从而导致用户的人身伤害以及设备严重损坏。",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.7036960124969482,
                "source": "local"
            },
            {
                "id": 468219061222798552,
                "file_title": "hak180产品安全手册",
                "title": "## 设备",
                "content": "## 设备\n\n•\t请勿在卡纸或有纸张散落在设备内部的情况下尝试使用本设备。纸张与定影单元长时间接触可能导致火灾。\n\n请勿使用任何易燃物品、任何类型的喷雾剂包含酒精或氨水的有机溶剂/液体来清洁本设备的内部或外部。否则可能导致火灾。请改用无绒干抹布。有关如何清洁本设备的说明，请参阅 。\n\n•\t请勿将本设备放在化学品附近，或者将本设备放置在可能会泼溅到化学品的位置。万一化学品接触本设备，则存在火灾或触电的风险。特别是有机溶剂或液体（如苯、油漆稀释剂、抛光剂或除臭剂）可能导致塑料盖和/或电缆溶解或分解，从而产生火灾或触电的风险。这些化学品或其他化学品可能导致本设备故障或褪色。",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.6913713216781616,
                "source": "local"
            }
        ]

    }
    # 执行RRF节点处理逻辑
    result = node(mock_state)
    # 打印最终融合排序结果日志
    logger.info(json_format_tool(result))