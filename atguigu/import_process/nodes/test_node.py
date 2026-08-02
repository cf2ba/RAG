from atguigu.import_process.base import NodeBase
from atguigu.tool.logger import logger


class Node(NodeBase):
    name = 'node_test'
    def process(self,state):
        logger.info(f"{self.name}要开始啦")
        return state
if __name__ == '__main__':
    init_state = {}
    n1 = Node()
    result = n1(init_state)
    logger.info(result)
