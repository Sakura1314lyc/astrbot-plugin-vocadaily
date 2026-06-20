import random
from astrbot.api.all import *
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 注册插件
@register("jrsq", "YourName", "发送今日推荐术曲(B站视频)", "1.0.0")
class JRSQPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 初始化定时器
        self.scheduler = AsyncIOScheduler()
        # 设定每天中午 12:00 触发 (可根据需要修改 cron 表达式)
        self.scheduler.add_job(self.scheduled_push, 'cron', hour=12, minute=0)
        self.scheduler.start()
        
        # 可以在这里初始化你的数据库连接或读取配置文件

    async def get_shuju_data(self) -> str:
        """
        数据获取层：获取一首术曲的B站信息
        这里可以是你自己维护的数据库，也可以是调 Bilibili API 获取某收藏夹内的随机视频
        """
        # 伪代码示例，实际可以替换为查库或请求 API
        fake_db = [
            {"title": "【初音未来】深海少女", "bv": "BV1xx411c7m9"},
            {"title": "【洛天依】达拉崩吧", "bv": "BV1xW411s715"}
        ]
        song = random.choice(fake_db)
        # 拼接 B 站链接，通常 QQ 等客户端会自动解析链接为卡片
        return f"🎵 今日术曲推荐：\n{song['title']}\n🔗 视频链接：https://www.bilibili.com/video/{song['bv']}"

    @filter.command("jrsq")
    async def handle_jrsq_command(self, event: AstrMessageEvent):
        """
        指令响应层：处理 /jrsq 指令
        """
        try:
            result_msg = await self.get_shuju_data()
            yield event.plain_result(result_msg)
        except Exception as e:
            # 增加鲁棒性，防止 API 挂掉导致报错
            yield event.plain_result(f"获取术曲失败了，请稍后再试呀。错误信息：{e}")

    async def scheduled_push(self):
        """
        定时触发层：主动发送消息到指定群聊或好友
        """
        result_msg = await self.get_shuju_data()
        
        # 获取你需要推送的群组列表 (假设你有一个目标群组 ID 列表)
        target_groups = ["123456789", "987654321"] 
        
        for group_id in target_groups:
            # 使用框架原生接口主动发送消息
            # 注意：不同平台（QQ, 微信）的 provider 名称可能不同，需根据你的 AstrBot 配置调整
            await self.context.send_message(
                target=group_id, 
                message=MessageChain([Plain(result_msg)])
            )