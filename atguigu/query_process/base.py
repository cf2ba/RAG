from abc import ABC, abstractclassmethod

from atguigu.tool.logger import logger


class NodeBase(ABC):
    name = 'node_base'
    def __init__(self):
        if self.name == 'node_base':
            raise Exception(f"子类{self.__class__.__name__}必须重写父类的name属性")
    @abstractclassmethod
    def process(self,state):
        pass
    #每个基础此抽象类的子类都必须重写process方法

#魔法方法不能随意修改如果可以直接将这个魔法方法设为抽象方法去用了 用这个魔法方法主要是后期实例对象可以直接加（）去调用，
    # 自动调用call方法的内容
    def __call__(self, state):
        try:
            logger.info(f"{self.name}开始执行了")
            result = self.process(state)
            logger.info(f"{self.name}执行结束")
            return result
        except Exception as e:
            logger.error(f"{self.name}执行失败")
            raise e
