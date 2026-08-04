import time
from collections import deque

import numpy as np

dq = deque(maxlen=30)  # maxlen令牌桶的最大长度
current_time = time.time()

a = np.random.randint(0, 255, 100)
image_with_summary_list = []

for image_with_context in a:
    # 调用大模型生成摘要
    # 令牌桶实现模型限流
    # 进入循环，先盲清一波过期的请求，如果队列中有超过一分钟的请求则清出令牌桶
    while dq and current_time - dq[0] > 60:
        dq.popleft()

    # 有两种情况 如果队列中所有令牌都没达到1分钟没有过期没有被清理的/队列中有过期的被清理的
    # 判断队列位置是否满了，如果满了就需要等待，如果没满就发送请求，把时间戳加入
    # 如果dq存在且令牌桶满，需要等待
    if dq and len(dq) == dq.maxlen:
        need_wait_time = 60 - (current_time - dq[0])
        if need_wait_time > 0:
            time.sleep(need_wait_time)  # 真正的等待
        current_time = time.time()
        while dq and current_time - dq[0] > 60:
            dq.popleft()